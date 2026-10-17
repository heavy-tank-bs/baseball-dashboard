"""Independently verify final-game coverage, annual/monthly counts and PA fixes.

Run with dashboard_requirements.txt installed. Reads saved assets only; never
fetches data or modifies reports. Optional --skip-parser-tests needs stdlib only.
"""
import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path
import sys

from verify_annual_totals import current_manifest, pitcher_additions

ROOT = Path(__file__).resolve().parent.parent
FINAL_GAMES = {'2021051134': '2026-10-07', '2021051699': '2026-10-08'}
BATTER_FIELDS = {
    'games': None, 'plateAppearances': 'plateAppearances', 'atBats': 'ab',
    'hits': 'hits', 'runs': 'runs', 'runsBattedIn': 'rbi', 'walks': 'walks',
    'hitByPitch': 'hitByPitch', 'sacBunts': 'sacBunts', 'steals': 'steals',
    'strikeouts': 'strikeouts', 'homeRuns': 'homeRuns', 'doubles': 'doubles',
    'triples': 'triples', 'singles': 'singles',
}


def read_json(name):
    return json.loads((ROOT / 'summary' / name).read_text(encoding='utf-8'))


def verify_parser_regressions():
    import build_woba_constants as woba
    assert woba.classify_event('送りバント失敗 一塁走者が二塁フォースアウト') == 'OUT'
    assert woba.classify_event('送りバント成功 1アウト二塁') == 'SH'
    game = {'gameId': 'fixture', 'date': '2026-10-08', 'homeTeam': '阪神', 'awayTeam': 'ヤクルト'}
    def html(result):
        return ('<section class="bb-liveText"><h3 class="bb-liveText__inning">1回表</h3>'
                '<div class="bb-liveText__item"><div class="bb-liveText__batter">'
                '<a class="bb-liveText__player" href="/npb/player/123/top">打者</a>'
                '<span class="bb-liveText__order">1番</span>'
                '<span class="bb-liveText__state">二死一塁</span></div>'
                f'<p class="bb-liveText__summary">{result}</p></div></section>')
    for result in ('一塁走者:盗塁を試みるもアウト 3アウト',
                   '一塁走者:けん制によりアウト 3アウト'):
        assert not woba.parse_game_text(game, html(result)), 'Unfinished PA counted after runner out'
    completed = woba.parse_game_text(game, html('空振り三振でバッターアウト 3アウト'))
    assert len(completed) == 1 and completed[0]['eventType'] == 'OUT', 'Completed inning-ending PA disappeared'
    print('PASS: failed bunt, successful sacrifice, unfinished runner-out PA, completed strikeout PA')


def verify_addition_regressions():
    stats = dict(innings='6', pitches='79', batters='23', hits='2', hr='0', k='7',
                 bb='2', hbp='0', runs='1', er='1')
    original = dict(gameId='old', date='2026-10-06', team='阪神', pitcherId='1', player='投手A', statline=stats)
    first = dict(original, gameId='new', date='2026-10-08')
    second = dict(first, team='広島', pitcherId='2', player='投手B')
    decisions = {'new': {'1': {'wins': 1}, '2': {'losses': 1}}}
    ids, rows = pitcher_additions([original], [original, first, second], decisions)
    assert ids == ['new'] and len(rows) == 2
    assert rows[0]['wins'] == 1 and rows[1]['losses'] == 1 and rows[0]['inningsOuts'] == 18
    changed = copy.deepcopy(original)
    changed['statline']['hits'] = '99'
    for entries in ([], [changed], [original, original], [original, first]):
        try:
            pitcher_additions([original], entries, decisions)
        except AssertionError:
            continue
        raise AssertionError('Pitcher preservation checker accepted corrupt fixture')
    print('PASS: new-game addition and old-game removal/change/duplicate rejection')


def verify():
    pitchers = current_manifest('manifest.js')
    for row in pitchers:
        assert (ROOT / 'summary' / row['detailPath']).is_file(), f'Missing detail: {row["id"]}'
        for page in row.get('pages', []):
            assert (ROOT / 'summary' / page['path']).is_file(), f'Missing PNG: {page["path"]}'
    print(f'PASS: all {len(pitchers)} pitcher detail references and PNG references exist')
    game_ids = {row['gameId'] for row in pitchers}
    cache = read_json('game_batting_cache.json')['games']
    assert set(FINAL_GAMES) <= game_ids, 'Final games absent from pitcher manifest'
    assert game_ids <= cache.keys(), 'Saved games missing batting cache'
    annual = [row for row in read_json('batter_totals.json')['players'] if row['year'] == '2026']
    expected, actual = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for game_id in game_ids:
        for team, players in cache[game_id].items():
            for key, player in players.items():
                if key != player['playerId']:
                    continue
                for field, source in BATTER_FIELDS.items():
                    expected[key][field] += int(player[source]) if source else 1
    for row in annual:
        for field in BATTER_FIELDS:
            value = row.get(field) or 0
            assert value >= 0, f'Negative annual count: {row["player"]} {field}'
            actual[row['batterId']][field] += value
            monthly = sum(month.get(field) or 0 for month in row['monthlySplits'])
            assert monthly == value, f'Monthly/annual mismatch: {row["player"]} {row["team"]} {field}'
    assert set(actual) == set(expected), 'Annual player identity set differs from game caches'
    for player_id in actual:
        assert actual[player_id] == expected[player_id], f'Per-player annual/cache mismatch: {player_id}'
    pitcher_fields = ('games', 'wins', 'losses', 'saves', 'holds', 'inningsOuts', 'batters',
                      'pitches', 'hits', 'homeRuns', 'strikeouts', 'walks', 'hitByPitch', 'runs', 'earnedRuns')
    for row in read_json('player_totals.json')['players']:
        if row['year'] != '2026':
            continue
        for field in pitcher_fields:
            assert sum(month.get(field) or 0 for month in row['monthlySplits']) == (row.get(field) or 0), f'Pitcher monthly/annual mismatch: {row["player"]} {field}'
    print(f'PASS: {len(game_ids)} games, {len(actual)} batters, 15 per-player annual/cache counts and all pitcher/batter monthly counts')
    events = read_json('sportsnavi_woba_events_2026.json')['events']
    for game_id, date in FINAL_GAMES.items():
        appearances = [row for row in pitchers if row['gameId'] == game_id]
        for row in appearances:
            raw_path = ROOT / 'generated' / row['team'] / date / f'{row["prefix"]}-dashboard.json'
            raw = json.loads(raw_path.read_text(encoding='utf-8'))
            assert len(raw['pitches']) == int(row['statline']['pitches']), f'Pitch count mismatch: {row["id"]}'
            assert len({p['pitchNo'] for p in raw['pitches']}) == len(raw['pitches']), 'Duplicate pitch number'
            assert all(p['left'] is not None and p['top'] is not None for p in raw['pitches']), 'Missing pitch location'
            assert len(row['pages']) == 4, f'Missing rendered pages: {row["id"]}'
        assert {row['date'] for row in appearances} == {date}, 'Final game date mismatch'
        assert len({row['team'] for row in appearances}) == 2, 'Final game pitching team missing'
        batters = [row for players in cache[game_id].values() for key, row in players.items() if key == row['playerId']]
        pa = sum(row['plateAppearances'] for row in batters)
        game_events = [event for event in events if str(event['gameId']) == game_id]
        assert len(game_events) == pa, f'Final-game event/official PA mismatch: {game_id}'
        print(f'PASS: {date} {game_id}: {len(appearances)} pitchers, {len(batters)} appearances, {pa} PA/events')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-parser-tests', action='store_true')
    args = parser.parse_args()
    verify_addition_regressions()
    if not args.skip_parser_tests:
        verify_parser_regressions()
    verify()
