"""Independently audit lineup metadata, split counts, and preserved site data.

Reads cached official HTML and committed baselines, with no network/dependencies.
Does not call either production batting-order parser or split aggregation helper.
"""
import argparse
from collections import Counter, defaultdict
import copy
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

from npb_boxscore_stats import _Tree, _cells, TEAMS

ROOT = Path(__file__).resolve().parent.parent
FIELDS = {'plateAppearances': 'plateAppearances', 'atBats': 'ab', 'hits': 'hits',
          'singles': 'singles', 'doubles': 'doubles', 'triples': 'triples',
          'homeRuns': 'homeRuns', 'walks': 'walks', 'hitByPitch': 'hitByPitch',
          'sacBunts': 'sacBunts', 'sacFlies': 'sacFlies', 'strikeouts': 'strikeouts'}


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))


def read(name, revision=None):
    content = (subprocess.check_output(['git', 'show', f'{revision}:summary/{name}'], cwd=ROOT).decode('utf-8')
               if revision else (ROOT / 'summary' / name).read_text(encoding='utf-8'))
    if name.endswith('.js'):
        content = content[content.index('{'):].rstrip(';\n')
    return json.loads(content)


def official_metadata(game, teams, roster):
    html = gzip.decompress((ROOT / f'.site-build/batting-order/{game["gameId"]}.html.gz').read_bytes()).decode('utf-8')
    tree = _Tree(html).root
    result = {}
    for table in tree.descendants('table'):
        if table.attrs.get('id') not in {'tablefix_t_b', 'tablefix_b_b'}:
            continue
        section = table.parent
        while section.tag != 'section':
            section = section.parent
        team = TEAMS[next(section.descendants('h4')).text().strip()]
        players = {key: row for key, row in teams[team].items() if key == row['playerId']}
        slot, starters = 0, []
        for row in table.direct('tbody')[0].direct('tr'):
            cells = _cells(row)
            literal = normalized(cells[0].text())
            if literal:
                assert literal in '123456789' and len(literal) == 1
                slot = int(literal)
                starters.append(slot)
            assert slot in range(1, 10)
            link = next(cells[2].descendants('a'))
            npb_id = re.search(r'/players/(\d+)\.html', link.attrs['href'])[1]
            full_name = normalized(roster.get(npb_id, ''))
            full_name = {'安田悠馬': 'YG安田'}.get(full_name, full_name)
            candidates = [key for key, player in players.items() if normalized(player['player']) == full_name]
            if not candidates:
                label = normalized(link.text())
                candidates = [key for key, player in players.items() if normalized(player['player']).startswith(label)]
            assert len(candidates) == 1, f'Ambiguous official player: {game["gameId"]} {team} {link.text()}'
            player_id = candidates[0]
            assert (team, player_id) not in result
            assert int(cells[3].text()) == players[player_id]['ab']
            assert int(cells[5].text()) == players[player_id]['hits']
            result[(team, player_id)] = {'battingOrder': slot, 'isStarter': bool(literal),
                                         'officialPlayerId': npb_id, 'officialOrderCell': cells[0].text().strip(),
                                         'officialPlayerLabel': link.text().strip()}
        assert starters == list(range(1, 10)), f'Expected exactly nine starters: {game["gameId"]} {team}'
        assert {key for parsed_team, key in result if parsed_team == team} == players.keys()
    assert len({team for team, player_id in result}) == 2
    return result


def rate(numerator, denominator):
    return round(numerator / denominator, 3) if denominator else None


def verify(report_path, baseline):
    entries = read('batter_manifest.js')['entries']
    old_entries = read('batter_manifest.js', baseline)['entries']
    assert [{k: v for k, v in row.items() if k not in {'battingOrder', 'isStarter'}} for row in entries] == old_entries, 'Unrelated batter manifest fields changed'
    cache = read('game_batting_cache.json')['games']
    games = json.loads((ROOT / '.site-build/audit/official-games.json').read_text(encoding='utf-8'))
    roster = json.loads((ROOT / '.site-build/npb-player-map.json').read_text(encoding='utf-8'))
    represented = {(e['gameId'], e['team'], e['batterId']) for e in entries}
    missing_entries = [{'gameId': game['gameId'], 'date': game['date'], 'team': team, 'batterId': key,
                        'player': row['player'], 'plateAppearances': row['plateAppearances'],
                        'battingOrder': row['battingOrder']}
                       for game in games for team, players in cache[game['gameId']].items()
                       for key, row in players.items()
                       if key == row['playerId'] and row['plateAppearances']
                       and (game['gameId'], team, key) not in represented]
    if missing_entries:
        print(json.dumps({'officialPARowsWithoutPitchManifest': missing_entries}, ensure_ascii=False), flush=True)
    assert {g['gameId'] for g in games} == {e['gameId'] for e in entries}
    official, official_rows = {}, 0
    sato_second_games = []
    for game in games:
        game_id = game['gameId']
        parsed = official_metadata(game, cache[game_id], roster)
        for (team, player_id), metadata in parsed.items():
            official[(game_id, team, player_id)] = metadata
            row = cache[game_id][team][player_id]
            assert all(row[key] == metadata[key] for key in ('battingOrder', 'isStarter'))
            for alias in cache[game_id][team].values():
                if alias['playerId'] == player_id:
                    assert all(alias[key] == metadata[key] for key in ('battingOrder', 'isStarter'))
            if player_id == '2000051' and metadata['battingOrder'] == 2:
                sato_second_games.append({**metadata, 'gameId': game_id, 'date': game['date'],
                                          'source': game['url'] + 'box.html', 'atBats': row['ab'], 'hits': row['hits']})
        official_rows += len(parsed)
    for entry in entries:
        metadata = official[(entry['gameId'], entry['team'], entry['batterId'])]
        assert all(entry[key] == metadata[key] for key in ('battingOrder', 'isStarter'))

    totals, old_totals = read('batter_totals.json'), read('batter_totals.json', baseline)
    def except_order_splits(players):
        result = copy.deepcopy(players)
        for player in result:
            if player.get('seasonDashboard'):
                player['seasonDashboard'].pop('byBattingOrder', None)
        return result
    assert except_order_splits(totals['players']) == except_order_splits(old_totals['players']), 'Annual/monthly counts, rates or other dashboard sections changed'
    assert [p for p in totals['players'] if p['year'] != '2026'] == [p for p in old_totals['players'] if p['year'] != '2026'], 'Historical seasons changed'
    for name in ('player_totals.json', 'woba_constants.json', 'sportsnavi_woba_events_2026.json'):
        assert read(name) == read(name, baseline), f'Unrelated asset changed: {name}'
    annual = [p for p in totals['players'] if p['year'] == '2026']
    row_for = {}
    for index, player in enumerate(annual):
        for team in player.get('sourceTeams') or player['teams']:
            assert (team, player['batterId']) not in row_for
            row_for[(team, player['batterId'])] = index
    counts = defaultdict(Counter)
    for game in games:
        for team, rows in cache[game['gameId']].items():
            for player_id, row in rows.items():
                if player_id != row['playerId'] or not row['plateAppearances']:
                    continue
                owner = row_for[(team, player_id)]
                for target, source in FIELDS.items():
                    counts[(owner, row['battingOrder'])][target] += row[source]
    checked_splits = 0
    for index, player in enumerate(annual):
        actual = (player.get('seasonDashboard') or {}).get('byBattingOrder', [])
        expected_slots = {slot for owner, slot in counts if owner == index}
        assert {row['label'] for row in actual} == {f'{slot}番' for slot in expected_slots}, f'Split labels differ: {player["player"]}'
        for split in actual:
            slot = int(split['label'][:-1])
            expected = counts[(index, slot)]
            mismatches = {field: {'expected': value, 'actual': split[field]}
                          for field, value in expected.items() if split[field] != value}
            if mismatches:
                print(json.dumps({'player': player['player'], 'batterId': player['batterId'],
                                  'slot': slot, 'mismatches': mismatches}, ensure_ascii=False), flush=True)
                raise AssertionError('Split counting stats differ from independent official cache sum')
            avg = rate(expected['hits'], expected['atBats'])
            obp_den = expected['atBats'] + expected['walks'] + expected['hitByPitch'] + expected['sacFlies']
            obp_num = expected['hits'] + expected['walks'] + expected['hitByPitch']
            bases = sum(expected[key] * weight for key, weight in [('singles', 1), ('doubles', 2), ('triples', 3), ('homeRuns', 4)])
            assert split['battingAverage'] == avg
            assert split['onBasePercentage'] == rate(obp_num, obp_den)
            assert split['sluggingPercentage'] == rate(bases, expected['atBats'])
            ops = round(obp_num / obp_den + bases / expected['atBats'], 3) if obp_den and expected['atBats'] else None
            assert split['ops'] == ops
            checked_splits += 1
    sato = next(p for p in annual if p['batterId'] == '2000051')
    assert all(row['label'] != '8番' for row in sato['seasonDashboard']['byBattingOrder'])
    assert sato_second_games, 'Official evidence for second batting slot is missing'
    report = {'baselineCommit': baseline, 'games': len(games), 'officialPlayerRows': official_rows,
              'manifestRows': len(entries), 'annualPlayers': len(annual), 'splitsChecked': checked_splits,
              'officialMetadataMatchesCacheAndManifest': True, 'splitCountsAndRatesMatchOfficialCache': True,
              'allOtherAnnualMonthlyAndDashboardFieldsUnchanged': True, 'historicalSeasonsUnchanged': True,
              'pitcherTotalsAndWobaAssetsUnchanged': True,
              'officialPARowsWithoutPitchManifest': missing_entries,
              'satoSplits': sato['seasonDashboard']['byBattingOrder'], 'satoSecondSlotOfficialEvidence': sato_second_games}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/batting-order-independent-verification.json')
    parser.add_argument('--baseline', default='HEAD')
    args = parser.parse_args()
    baseline = subprocess.check_output(['git', 'rev-parse', args.baseline], cwd=ROOT).decode().strip()
    verify(args.report, baseline)
