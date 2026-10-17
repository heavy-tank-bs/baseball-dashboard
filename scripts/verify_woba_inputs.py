"""Independently reconcile published PA events with annual/monthly wOBA inputs.

Standard library only. No network or data mutation; --report optionally saves
the comparison report. Team membership preserves cross-league transfer rows.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
AB_EVENTS = {'1B', '2B', '3B', 'HR', 'OUT', 'ROE'}
DENOMINATOR_EVENTS = AB_EVENTS | {'uBB', 'HBP', 'SF'}


def read_json(name):
    return json.loads((ROOT / 'summary' / name).read_text(encoding='utf-8'))


def stats(counts):
    return {'plateAppearances': sum(counts.values()),
            'atBats': sum(counts[k] for k in AB_EVENTS),
            'singles': counts['1B'], 'doubles': counts['2B'], 'triples': counts['3B'],
            'homeRuns': counts['HR'], 'walks': counts['IBB'] + counts['uBB'],
            'intentionalWalks': counts['IBB'], 'unintentionalWalks': counts['uBB'],
            'hitByPitch': counts['HBP'], 'sacBunts': counts['SH'], 'sacFlies': counts['SF'],
            'wobaDenominator': sum(counts[k] for k in DENOMINATOR_EVENTS)}


def verify_derived(players, constants):
    """Recalculate league baselines and wRC independently of the site builder."""
    weights = {'unintentionalWalks': 'wBB', 'hitByPitch': 'wHBP', 'singles': 'w1B',
               'doubles': 'w2B', 'triples': 'w3B', 'homeRuns': 'wHR'}
    def numerator(row):
        return sum((row.get(field) or 0) * constants[weight] for field, weight in weights.items())
    def denominator(row):
        return sum(row.get(field) or 0 for field in ('atBats', 'unintentionalWalks', 'hitByPitch', 'sacFlies'))
    rows = [(player, None, player) for player in players]
    rows += [(player, month['month'], month) for player in players for month in player['monthlySplits']]
    leagues = defaultdict(Counter)
    for player, month, row in rows:
        group = leagues[(player['league'], month)]
        group['numerator'] += numerator(row)
        group['denominator'] += denominator(row)
        group['runs'] += row.get('runs') or 0
        group['pa'] += row.get('plateAppearances') or 0
    differences = []
    for player, month, row in rows:
        group = leagues[(player['league'], month)]
        denom, pa = denominator(row), row.get('plateAppearances') or 0
        expected = {'wrc': None, 'wrcPlus': None}
        if denom and group['denominator'] and group['pa']:
            lg_woba = group['numerator'] / group['denominator']
            run_rate = group['runs'] / group['pa']
            batting_rate = (numerator(row) / denom - lg_woba) / constants['wOBAScale'] + run_rate
            expected['wrc'] = batting_rate * pa if pa else None
            if run_rate and row.get('effectiveParkFactor') is not None:
                expected['wrcPlus'] = 100 * batting_rate / run_rate + 100 - row['effectiveParkFactor']
        for field, value in expected.items():
            actual = row.get(field)
            # Stored PF and wRC+ each round to one decimal; their combined
            # representation uncertainty is at most 0.1 wRC+ points.
            tolerance = 0.100001 if field == 'wrcPlus' else 0.050001
            if (actual is None) != (value is None) or (actual is not None and abs(actual - value) > tolerance):
                differences.append({'batterId': player['batterId'], 'player': player['player'],
                                    'team': player['team'], 'month': month, 'field': field,
                                    'expected': value, 'actual': actual})
    return {'rows': len(rows), 'metricsChecked': len(rows) * 2,
            'differenceCount': len(differences), 'differences': differences}


def verify_pitcher_inputs(season):
    sync = json.loads((ROOT / f'docs/intentional-walk-sync-{season}.json').read_text(encoding='utf-8'))
    baseline = sync['baselineCommit']
    old = json.loads(subprocess.check_output(['git', 'show', f'{baseline}:summary/player_totals.json'], cwd=ROOT))
    new = read_json('player_totals.json')
    old_rows = [p for p in old['players'] if p['year'] == season]
    new_rows = [p for p in new['players'] if p['year'] == season]
    # Checked against the official pitching-change rows in the cached NPB
    # play-by-play: 2021039189 inning 9 Moriura, inning 10 Endoh.
    # Akahoshi's 2021038761 IBB already existed; only the batter ID was absent.
    expected_deltas = {'2000061': ('2026-07', 1), '1700072': ('2026-07', 2)} if season == '2026' else {}
    identity = lambda p: (p['pitcherId'], p.get('aggregationKey') or p['team'])
    previous = {identity(p): p for p in old_rows}
    assert previous.keys() == {identity(p) for p in new_rows}, 'Pitcher identities changed'
    fields = ('inningsOuts', 'earnedRuns', 'homeRuns', 'unintentionalWalks', 'hitByPitch', 'strikeouts')
    leagues = defaultdict(Counter)
    for player in new_rows:
        for field in fields:
            leagues[player['league']][field] += player.get(field) or 0
    constants = {}
    for league, counts in leagues.items():
        ip = counts['inningsOuts'] / 3
        component = 13 * counts['homeRuns'] + 3 * (counts['unintentionalWalks'] + counts['hitByPitch']) - 2 * counts['strikeouts']
        constants[league] = (9 * counts['earnedRuns'] - component) / ip
    differences, affected = [], []
    checked = 0
    for player in new_rows:
        old_player = previous[identity(player)]
        old_months = {m['month']: m for m in old_player['monthlySplits']}
        entries = [(None, player, old_player)] + [(m['month'], m, old_months[m['month']]) for m in player['monthlySplits']]
        target_month, delta = expected_deltas.get(player['pitcherId'], ('', 0))
        for month, row, before in entries:
            expected_delta = delta if month is None or month == target_month else 0
            for field, change in [('intentionalWalks', expected_delta), ('unintentionalWalks', -expected_delta)]:
                expected = (before.get(field) or 0) + change
                if (row.get(field) or 0) != expected:
                    differences.append({'player': player['player'], 'month': month, 'field': field,
                                        'expected': expected, 'actual': row.get(field)})
            ip = (row.get('inningsOuts') or 0) / 3
            expected_fip = None
            if ip:
                expected_fip = ((13 * row['homeRuns'] + 3 * (row['unintentionalWalks'] + row['hitByPitch'])
                                 - 2 * row['strikeouts']) / ip + constants[player['league']])
            actual = row.get('fip')
            if (actual is None) != (expected_fip is None) or (actual is not None and abs(actual - expected_fip) > 0.005001):
                differences.append({'player': player['player'], 'month': month, 'field': 'fip',
                                    'expected': expected_fip, 'actual': actual})
            checked += 1
        if player['pitcherId'] in expected_deltas or player['pitcherId'] == '2103689':
            affected.append({'pitcherId': player['pitcherId'], 'player': player['player'],
                             'intentionalWalksBefore': old_player['intentionalWalks'],
                             'intentionalWalksAfter': player['intentionalWalks'],
                             'expectedAddedIntentionalWalks': delta})
    return {'baselineCommit': baseline, 'rows': checked, 'leagueFipConstants': constants,
            'affectedPitchers': affected, 'differenceCount': len(differences), 'differences': differences}


def verify(season, report_path=None, check_derived=False):
    payload = read_json(f'sportsnavi_woba_events_{season}.json')
    events = payload['events']
    totals = read_json('batter_totals.json')
    players = [p for p in totals['players'] if p['year'] == season]
    manifest_text = (ROOT / 'summary/manifest.js').read_text(encoding='utf-8')
    manifest = json.loads(manifest_text[manifest_text.index('{'):].rstrip(';\n'))
    game_ids = {e['gameId'] for e in manifest['entries'] if e['date'].startswith(season)}
    assert {e['gameId'] for e in events} == game_ids, 'Event game coverage differs from manifest'
    assert all(e['date'].startswith(season) for e in events), 'Unexpected event season'
    assert payload.get('eventCount') == len(events), 'Event count metadata mismatch'
    assert all(e['eventType'] in DENOMINATOR_EVENTS | {'IBB', 'SH', 'INT'} for e in events), 'Unknown event category'

    identities = defaultdict(list)
    for index, player in enumerate(players):
        for team in player.get('teams') or [player['team']]:
            identities[(player['batterId'], team)].append(index)
    counts, monthly = defaultdict(Counter), defaultdict(Counter)
    for event in events:
        candidates = identities[(event['batterId'], event['battingTeam'])]
        assert len(candidates) == 1, f'PA maps to {len(candidates)} annual rows: {event["batterId"]} {event["battingTeam"]}'
        index = candidates[0]
        counts[index][event['eventType']] += 1
        monthly[(index, event['date'][:7])][event['eventType']] += 1

    differences = []
    checked_months = 0
    def compare(index, row, expected, month=None):
        actual = {key: int(row.get(key) or 0) for key in expected}
        actual['wobaDenominator'] = (actual['atBats'] + actual['unintentionalWalks']
                                     + actual['hitByPitch'] + actual['sacFlies'])
        for field, value in expected.items():
            if actual[field] != value:
                player = players[index]
                differences.append({'batterId': player['batterId'], 'player': player['player'],
                                    'team': player['team'], 'month': month, 'field': field,
                                    'expected': value, 'actual': actual[field]})
    for index, player in enumerate(players):
        compare(index, player, stats(counts[index]))
        actual_months = {m['month']: m for m in player.get('monthlySplits', [])}
        expected_months = {month for (owner, month) in monthly if owner == index}
        assert expected_months <= actual_months.keys(), f'Missing monthly rows: {player["player"]}'
        for month, row in actual_months.items():
            compare(index, row, stats(monthly[(index, month)]), month)
            checked_months += 1

    constants = read_json('woba_constants.json')['byYear'][season]
    all_counts = Counter(e['eventType'] for e in events)
    assert Counter(constants['eventCounts']) == all_counts, 'Constant event counts differ'
    assert constants['denominator'] == stats(all_counts)['wobaDenominator'], 'Constant denominator differs'
    assert not constants.get('missingRunValueCounts'), 'Some events lack run expectancy values'
    assert len(constants['stateSampleCounts']) == 24, 'Not all 24 base/out states observed'
    old = json.loads(subprocess.check_output(['git', 'show', 'HEAD:summary/batter_totals.json'], cwd=ROOT))
    assert [p for p in old['players'] if p['year'] != season] == [p for p in totals['players'] if p['year'] != season], 'Historical batter totals changed'
    report = {'season': season, 'games': len(game_ids), 'plateAppearances': len(events),
              'annualRows': len(players), 'monthlyRows': checked_months,
              'eventCounts': dict(all_counts), 'historicalSeasonsUnchanged': True,
              'differenceCount': len(differences), 'differences': differences}
    affected_ibb = {(d['batterId'], d['month']) for d in differences
                    if d['field'] == 'intentionalWalks' and d['month']}
    report['intentionalWalkEvidence'] = [
        {key: e[key] for key in ('gameId', 'date', 'inning', 'half', 'battingTeam', 'batterId', 'batter', 'result')}
        for e in events if e['eventType'] == 'IBB' and (e['batterId'], e['date'][:7]) in affected_ibb]
    if check_derived:
        report['derived'] = verify_derived(players, constants)
        report['pitchers'] = verify_pitcher_inputs(season)
    if report_path:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: (dict(v, differences=v['differences'][:20]) if k in {'derived', 'pitchers'} else v)
                      for k, v in report.items() if k != 'differences'}, ensure_ascii=False, indent=2))
    if differences:
        print(json.dumps(differences[:30], ensure_ascii=False, indent=2))
    return not differences and not report.get('derived', {}).get('differenceCount') and not report.get('pitchers', {}).get('differenceCount')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', default='2026')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--check-derived', action='store_true', help='Also independently check annual/monthly wRC and wRC+')
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.season, args.report, args.check_derived) else 1)
