"""Verify complete wOBA coverage, preserved counts and refreshed wRC/wRC+."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess

import build_woba_constants as woba
from refresh_woba_season import inputs, audit

ROOT = Path(__file__).resolve().parent.parent


def read(name):
    return json.loads((ROOT / 'summary' / name).read_text(encoding='utf-8'))


def committed(name):
    return json.loads(subprocess.check_output(['git', 'show', f'HEAD:summary/{name}'], cwd=ROOT).decode('utf-8'))


def rate(row, constants):
    denominator = sum(row[k] for k in ('atBats', 'unintentionalWalks', 'hitByPitch', 'sacFlies'))
    if not denominator:
        return None
    pairs = [('wBB', 'unintentionalWalks'), ('wHBP', 'hitByPitch'), ('w1B', 'singles'),
             ('w2B', 'doubles'), ('w3B', 'triples'), ('wHR', 'homeRuns')]
    return sum(constants[weight] * row[field] for weight, field in pairs) / denominator


def differences(before, after, path=''):
    if isinstance(before, dict) and isinstance(after, dict):
        return [item for key in before.keys() | after.keys()
                for item in differences(before.get(key), after.get(key), f'{path}.{key}')]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [item for index, (a, b) in enumerate(zip(before, after))
                for item in differences(a, b, f'{path}[{index}]')]
    return [] if before == after else [(path, before, after)]


def main():
    # A full rebuild may refresh timestamps on unchanged supporting assets.
    for name in ('batter_manifest.js', 'park_factors.json'):
        saved = subprocess.check_output(['git', 'show', f'HEAD:summary/{name}'], cwd=ROOT).decode('utf-8')
        current_text = (ROOT / 'summary' / name).read_text(encoding='utf-8')
        def data(content):
            result = json.loads(content[content.index('{'):].rstrip(';\n'))
            result.pop('updatedAt', None)
            return result
        assert data(saved) == data(current_text), f'Unrelated supporting asset changed: {name}'
    games, batting = inputs('2026')
    events = read('sportsnavi_woba_events_2026.json')['events']
    by_game = defaultdict(list)
    for event in events:
        by_game[event['gameId']].append(event)
        assert event['preState'][0] in '012', 'PA begins after inning ends'
        assert event['postState'][0] in '0123', 'Invalid post-state'
        assert event['runsBefore'] <= event['runsAfter'] <= event['inningRuns'], 'Invalid runs'
        assert int(event['postState'][0]) >= int(event['preState'][0]), 'Outs decreased'
    assert len(games) == 858 and set(by_game) == {g['gameId'] for g in games}
    for game in games:
        assert not audit(game, by_game[game['gameId']], batting[game['gameId']]), f'Official mismatch: {game["gameId"]}'
    constants = read('woba_constants.json')['byYear']['2026']
    assert constants['games'] == 858 and constants['coverageComplete'] and not constants['fetchErrors']
    expected = woba.calculate_constants_for_year('2026', events)
    for key, value in expected.items():
        if key == 'source':
            continue
        assert constants[key] == value, f'Constants differ from saved events: {key}'
    assert constants['missingRunValueCounts'] == {}, 'Events silently excluded due to missing RE state'
    assert len(constants['stateSampleCounts']) == 24 and all(constants['stateSampleCounts'].values())
    assert all(constants[k] > 0 for k in ('wBB','wHBP','w1B','w2B','w3B','wHR','wOBAScale'))
    old, new = committed('batter_totals.json'), read('batter_totals.json')
    assert [r for r in old['players'] if r['year']=='2025'] == [r for r in new['players'] if r['year']=='2025']
    old_rows = {(r['year'], r.get('aggregationKey') or r['batterId'] or r['player'], r['team']): r for r in old['players']}
    def without_rates(row):
        return {key: ([without_rates(m) for m in value] if key == 'monthlySplits' else value)
                for key, value in row.items() if key not in ('wrc', 'wrcPlus', 'intentionalWalks', 'unintentionalWalks')}
    for row in new['players']:
        previous = old_rows[(row['year'], row.get('aggregationKey') or row['batterId'] or row['player'], row['team'])]
        unexpected = differences(without_rates(previous), without_rates(row))
        assert not unexpected, f'Non-wOBA data changed: {row["player"]} {unexpected[:10]}'
    current = [r for r in new['players'] if r['year'] == '2026']
    league_counts = defaultdict(Counter)
    fields = ('atBats','unintentionalWalks','hitByPitch','sacFlies','singles','doubles','triples','homeRuns','runs','plateAppearances')
    for row in current:
        for field in fields:
            league_counts[row['league']][field] += row[field]
    verified = 0
    for row in current:
        counts = league_counts[row['league']]
        league_rate = rate(counts, constants)
        run_rate = counts['runs'] / counts['plateAppearances']
        player_rate = rate(row, constants)
        if player_rate is None or not row['plateAppearances']:
            assert row['wrc'] is None and row['wrcPlus'] is None
            continue
        above = (player_rate - league_rate) / constants['wOBAScale']
        assert row['wrc'] == round((above + run_rate) * row['plateAppearances'], 1), f'wRC mismatch: {row["player"]}'
        # Stored park factors are rounded to 0.1; permit the corresponding 0.1 wRC+ rounding spread.
        expected_plus = ((above + run_rate) / run_rate + 1 - row['effectiveParkFactor']/100) * 100
        assert abs(row['wrcPlus'] - expected_plus) <= 0.11, f'wRC+ mismatch: {row["player"]}'
        verified += 1
    # Correcting four missing IBB also changes pitcher FIP and league FIP constants.
    old_pitchers, new_pitchers = committed('player_totals.json'), read('player_totals.json')
    assert [r for r in old_pitchers['players'] if r['year']=='2025'] == [r for r in new_pitchers['players'] if r['year']=='2025']
    def without_fip(row):
        return {key: ([without_fip(m) for m in value] if key == 'monthlySplits' else value)
                for key, value in row.items() if key not in ('fip', 'fipConstant', 'intentionalWalks', 'unintentionalWalks')}
    old_pitcher_rows = {(r['year'], r.get('aggregationKey') or r['pitcherId'] or r['player'], r['team']): r for r in old_pitchers['players']}
    for row in new_pitchers['players']:
        previous = old_pitcher_rows[(row['year'], row.get('aggregationKey') or row['pitcherId'] or row['player'], row['team'])]
        unexpected = differences(without_fip(previous), without_fip(row))
        assert not unexpected, f'Unrelated pitcher data changed: {row["player"]} {unexpected[:10]}'
    print(f'PASS: 858 games, {len(events)} PA, all 24 states, complete official-count audits')
    print(f'PASS: constants recomputed from saved events; {verified} annual wRC/wRC+ rows; 2025 and unrelated counts preserved')


if __name__ == '__main__':
    main()
