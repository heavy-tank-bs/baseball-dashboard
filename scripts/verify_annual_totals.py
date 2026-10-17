"""Check a rebuilt dataset against the committed data and game manifests."""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def manifest(content):
    return json.loads(content[content.index('{'):].rstrip(';\n'))['entries']


def committed_manifest(name):
    return manifest(subprocess.check_output(['git', 'show', f'HEAD:summary/{name}'], cwd=ROOT).decode('utf-8'))


def current_manifest(name):
    return manifest((ROOT / 'summary' / name).read_text(encoding='utf-8'))


def pitcher_additions(old_entries, new_entries, decisions):
    """Validate retained appearances and independently count only new games."""
    def appearance_key(entry):
        return (entry['gameId'], entry['team'], entry.get('pitcherId') or entry['player'])
    old = {appearance_key(entry): entry for entry in old_entries}
    new = {appearance_key(entry): entry for entry in new_entries}
    assert len(old) == len(old_entries) and len(new) == len(new_entries), 'Duplicate pitcher appearance'
    assert old.keys() <= new.keys(), 'Previously collected pitcher appearance disappeared'
    for key, previous in old.items():
        assert previous['statline'] == new[key]['statline'], f'Existing pitcher statline changed: {key}'
        assert previous['date'] == new[key]['date'], f'Existing game date changed: {key}'
    old_ids = {entry['gameId'] for entry in old_entries}
    new_ids = {entry['gameId'] for entry in new_entries} - old_ids
    added = [entry for key, entry in new.items() if key not in old]
    assert all(entry['gameId'] in new_ids for entry in added), 'Unexpected added appearance in an existing game'
    for game_id in new_ids:
        assert len({e['team'] for e in added if e['gameId'] == game_id}) == 2, f'New game lacks two pitching teams: {game_id}'
    rows = []
    stat_fields = {'batters': 'batters', 'pitches': 'pitches', 'hits': 'hits',
                   'homeRuns': 'hr', 'strikeouts': 'k', 'walks': 'bb',
                   'hitByPitch': 'hbp', 'runs': 'runs', 'earnedRuns': 'er'}
    for entry in added:
        stats = entry['statline']
        innings = re.fullmatch(r'(\d+)(?:\.([012]))?', str(stats['innings']))
        assert innings, f'Invalid innings notation: {stats["innings"]}'
        row = {'year': entry['date'][:4], 'pitcherId': entry.get('pitcherId') or '',
               'player': entry['player'], 'games': 1,
               'inningsOuts': int(innings[1]) * 3 + int(innings[2] or 0)}
        for field, source in stat_fields.items():
            value = str(stats[source]).strip()
            assert value.isdigit(), f'Invalid new-game count: {entry["gameId"]} {source}={value}'
            row[field] = int(value)
        game_decisions = decisions.get(entry['gameId'])
        assert isinstance(game_decisions, dict) and game_decisions, f'Missing new-game decisions: {entry["gameId"]}'
        decision = game_decisions.get(entry.get('pitcherId')) or game_decisions.get(entry['player']) or {}
        for field in ('wins', 'losses', 'saves', 'holds'):
            row[field] = int(decision.get(field) or 0)
            assert row[field] in (0, 1), f'Invalid pitching decision: {field}'
        rows.append(row)
    return sorted(new_ids), rows


def verify(expected_added_games=None, write_report=True):
    report = {}
    old_pitchers, new_pitchers = committed_manifest('manifest.js'), current_manifest('manifest.js')
    decisions = json.loads((ROOT / 'summary/game_decisions_cache.json').read_text(encoding='utf-8'))['games']
    added_game_ids, added_pitchers = pitcher_additions(old_pitchers, new_pitchers, decisions)
    if expected_added_games is not None:
        assert set(added_game_ids) == set(expected_added_games), f'Unexpected added game IDs: {added_game_ids}'
    old_games, new_games = committed_manifest('batter_manifest.js'), current_manifest('batter_manifest.js')
    cache = json.loads((ROOT / 'summary/game_batting_cache.json').read_text(encoding='utf-8'))
    dates = {entry['gameId']: entry['date'] for entry in new_pitchers}
    added_batters = []
    added_batter_entries = {(entry['gameId'], entry['team'], entry['batterId']): entry for entry in new_games if entry['gameId'] in added_game_ids}
    batter_fields = {'plateAppearances': 'plateAppearances', 'atBats': 'ab', 'runs': 'runs',
                     'hits': 'hits', 'homeRuns': 'homeRuns', 'runsBattedIn': 'rbi',
                     'walks': 'walks', 'hitByPitch': 'hitByPitch', 'sacBunts': 'sacBunts',
                     'steals': 'steals', 'strikeouts': 'strikeouts'}
    for game_id in added_game_ids:
        teams = cache['games'][game_id]
        assert len(teams) == 2 and all(teams.values()), f'Incomplete added-game batting cache: {game_id}'
        for team, players in teams.items():
            for key, player in players.items():
                if key != (player.get('playerId') or player['player']):
                    continue
                row = {'year': dates[game_id][:4], 'batterId': player.get('playerId') or '', 'player': player['player'], 'games': 1}
                row.update({field: int(player[source]) for field, source in batter_fields.items()})
                entry = added_batter_entries.get((game_id, team, player.get('playerId')), {})
                plates = (entry.get('dashboard') or {}).get('plateAppearances') or []
                row['sacFlies'] = sum('犠飛' in (plate.get('result') or '') for plate in plates)
                added_batters.append(row)
    for filename, id_key, fields in [
        ('player_totals.json', 'pitcherId', ['games', 'wins', 'losses', 'saves', 'holds', 'inningsOuts', 'batters', 'pitches', 'hits', 'homeRuns', 'strikeouts', 'walks', 'hitByPitch', 'runs', 'earnedRuns']),
        ('batter_totals.json', 'batterId', ['games', 'plateAppearances', 'atBats', 'runs', 'hits', 'homeRuns', 'runsBattedIn', 'walks', 'hitByPitch', 'sacBunts', 'sacFlies', 'steals', 'strikeouts']),
    ]:
        old = json.loads(subprocess.check_output(['git', 'show', f'HEAD:summary/{filename}'], cwd=ROOT))
        new = json.loads((ROOT / 'summary' / filename).read_text(encoding='utf-8'))
        assert [r for r in old['players'] if r['year'] == '2025'] == [r for r in new['players'] if r['year'] == '2025'], 'Historical season changed'
        def sums(rows):
            result = defaultdict(lambda: defaultdict(int))
            for row in rows:
                key = (row['year'], row.get(id_key) or row['player'])
                for field in fields:
                    result[key][field] += row.get(field) or 0
            return result
        a, b = sums(old['players']), sums(new['players'])
        added_counts = sums(added_pitchers if id_key == 'pitcherId' else added_batters)
        differences = []
        unexpected_differences = []
        for key in sorted(a.keys() | b.keys() | added_counts.keys()):
            for field in fields:
                if a[key][field] != b[key][field]:
                    differences.append({'player': key, 'metric': field, 'before': a[key][field], 'after': b[key][field]})
                expected = a[key][field] + added_counts[key][field]
                if expected != b[key][field]:
                    unexpected_differences.append({'player': key, 'metric': field, 'expected': expected, 'after': b[key][field]})
        identities = [(r['year'], r.get('aggregationKey') or r.get(id_key) or f"{r['team']}::{r['player']}") for r in new['players']]
        assert len(identities) == len(set(identities)), 'Duplicate annual selection key'
        transfers = [r for r in old['players'] if len(r.get('teams', [])) > 1]
        transfer_keys = {(r['year'], r.get(id_key) or r['player']) for r in transfers}
        assert not [d for d in unexpected_differences if tuple(d['player']) in transfer_keys], 'Transfer counting stats differ from baseline plus added games'
        if id_key == 'pitcherId':
            assert not unexpected_differences, f'Pitcher counting stats differ from baseline plus added games: {unexpected_differences[:5]}'
        report[filename] = {'differences': differences, 'differencesExcludingAddedGames': unexpected_differences, 'transfers': [
            {k: row.get(k) for k in ['player', 'team', 'league', 'games', 'innings', 'atBats', 'hits', 'wins', 'losses']}
            for transfer in transfers for row in new['players'] if row['year'] == transfer['year'] and row.get(id_key) == transfer.get(id_key)
        ]}
    old_lines = {(e['gameId'], e['team'], e['batterId']): e for e in old_games}
    corrections = []
    for entry in new_games:
        row = cache['games'][entry['gameId']][entry['team']][entry['batterId']]
        assert all(value == row.get(key) for key, value in entry['statline'].items()), 'Game stat line differs from official cache'
        key = (entry['gameId'], entry['team'], entry['batterId'])
        previous = old_lines.get(key)
        if previous and previous['statline'] != entry['statline']:
            corrections.append({'date': entry['date'], 'gameId': entry['gameId'], 'team': entry['team'], 'player': entry['player'], 'before': previous['statline'], 'after': entry['statline']})
    report['verification'] = {
        'status': 'passed', 'historical2025Unchanged': True,
        'existingPitcherAppearancesAndStatlinesUnchanged': True,
        'pitcherCountingStatsUnchanged': not report['player_totals.json']['differences'],
        'pitcherCountingStatsMatchBaselinePlusAddedGames': True,
        'transferredCombinedCountingStatsMatchBaselinePlusAddedGames': True,
        'allBatterGameStatlinesMatchOfficialCache': True,
        'addedGameIds': added_game_ids, 'addedPitcherAppearances': len(added_pitchers),
        'addedBatterAppearances': len(added_batters),
        'correctedBatterGameLines': len(corrections),
        'correctedGames': len({e['gameId'] for e in corrections}),
    }
    report['officialGameCorrections'] = corrections
    target = ROOT / 'docs/aggregation-verification.json'
    if write_report:
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['verification'], ensure_ascii=False, indent=2))
    for filename in ['player_totals.json', 'batter_totals.json']:
        print(filename, 'reviewed baseline differences:', len(report[filename]['differences']))
        print(json.dumps(report[filename]['transfers'], ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-added-game', action='append', help='Require exactly these added game IDs; repeat for multiple games.')
    parser.add_argument('--no-write', action='store_true', help='Validate without updating the JSON report.')
    args = parser.parse_args()
    verify(args.expected_added_game, not args.no_write)
