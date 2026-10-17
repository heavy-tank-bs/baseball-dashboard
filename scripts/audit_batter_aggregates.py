"""Independently audit every batter's published counts, rates and season splits.

Uses official cached box scores and NPB play-by-play, never the builder's
classification or aggregation functions. Reports all discrepancies as JSON.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
AB = {'1B', '2B', '3B', 'HR', 'OUT', 'ROE'}
HITS = {'1B', '2B', '3B', 'HR'}
FIELDS = {'plateAppearances': 'plateAppearances', 'atBats': 'ab', 'hits': 'hits',
          'singles': 'singles', 'doubles': 'doubles', 'triples': 'triples',
          'homeRuns': 'homeRuns', 'walks': 'walks', 'hitByPitch': 'hitByPitch',
          'sacBunts': 'sacBunts', 'sacFlies': 'sacFlies', 'strikeouts': 'strikeouts',
          'runs': 'runs', 'runsBattedIn': 'rbi', 'steals': 'steals'}
SPLIT_FIELDS = tuple(k for k in FIELDS if k not in {'runs', 'runsBattedIn', 'steals'})
SPLITS = ('byOpponent', 'byStadium', 'byPitchType', 'byVelocity', 'byPitcherHand',
          'byBattingOrder', 'byPlateAppearance', 'byStrikeCount')


def read(name):
    return json.loads((ROOT / 'summary' / name).read_text(encoding='utf-8'))


def manifest(name):
    text = (ROOT / 'summary' / name).read_text(encoding='utf-8')
    return json.loads(text[text.index('{'):].rstrip(';\n'))['entries']


def event_stats(event):
    kind = event['eventType']
    return {'plateAppearances': 1, 'atBats': int(kind in AB), 'hits': int(kind in HITS),
            'singles': int(kind == '1B'), 'doubles': int(kind == '2B'),
            'triples': int(kind == '3B'), 'homeRuns': int(kind == 'HR'),
            'walks': int(kind in {'IBB', 'uBB'}), 'hitByPitch': int(kind == 'HBP'),
            'sacBunts': int(kind == 'SH'), 'sacFlies': int(kind == 'SF'),
            'strikeouts': int('三振' in event['result'] or '振り逃げ' in event['result'])}


def rates(row):
    n = lambda field: row.get(field) or 0
    ratio = lambda a, b: a / b if b else None
    avg = ratio(n('hits'), n('atBats'))
    obp = ratio(n('hits') + n('walks') + n('hitByPitch'),
                n('atBats') + n('walks') + n('hitByPitch') + n('sacFlies'))
    slg = ratio(n('singles') + 2*n('doubles') + 3*n('triples') + 4*n('homeRuns'), n('atBats'))
    return {'battingAverage': avg, 'onBasePercentage': obp, 'sluggingPercentage': slg,
            'ops': obp + slg if obp is not None and slg is not None else None,
            'isoDiscipline': obp - avg if obp is not None and avg is not None else None,
            'isoPower': slg - avg if slg is not None and avg is not None else None,
            'babip': ratio(n('hits')-n('homeRuns'), n('atBats')-n('strikeouts')-n('homeRuns')+n('sacFlies')),
            'scoringPositionBattingAverage': ratio(n('scoringPositionHits'), n('scoringPositionAtBats'))}


def audit(season):
    all_players = read('batter_totals.json')['players']
    players = [p for p in all_players if p['year'] == season]
    events = read(f'sportsnavi_woba_events_{season}.json')['events']
    boxes = read('game_batting_cache.json')['games']
    contexts = {g['gameId']: g for g in read(f'sportsnavi_game_context_{season}.json')['games']}
    entries = manifest('batter_manifest.js')
    dates = {e['gameId']: e['date'] for e in events}
    owner = {}
    for i, p in enumerate(players):
        for team in p.get('teams') or [p['team']]:
            key = (p['batterId'], team)
            assert key not in owner, f'Ambiguous player identity {key}'
            owner[key] = i
    differences = []
    checks = Counter()
    def compare(i, scope, actual, expected, rate=False):
        for field, value in expected.items():
            if rate and field not in actual:
                continue
            checks['rate' if rate else 'count'] += 1
            got = actual.get(field)
            mismatch = ((got is None) != (value is None) or
                        (got is not None and abs(got-value) > (0.000501 if rate else 0)))
            if mismatch:
                differences.append({'player': players[i]['player'], 'batterId': players[i]['batterId'],
                                    'team': players[i]['team'], 'scope': scope, 'field': field,
                                    'actual': got, 'expected': value})
    official = defaultdict(Counter)
    opponents = defaultdict(Counter)
    stadiums = defaultdict(Counter)
    lineup_slots = defaultdict(Counter)
    plate_ordinals = defaultdict(Counter)
    expected_plates = {}
    game_ordinal = Counter()
    for gid in dates:
        teams = boxes[gid]
        for team, rows in teams.items():
            opponent = next(t for t in teams if t != team)
            for key, stats in rows.items():
                if key != stats.get('playerId'):
                    continue
                i = owner[(key, team)]
                values = {k: stats.get(v, 0) for k, v in FIELDS.items()}
                for month in (None, dates[gid][:7]):
                    official[i, month].update(values)
                    official[i, month]['games'] += 1
                opponents[i, opponent].update({k: values[k] for k in SPLIT_FIELDS})
                stadiums[i, contexts[gid].get('stadium') or '-'].update({k: values[k] for k in SPLIT_FIELDS})
                slot = stats.get('battingOrder')
                label = f'{slot}番' if slot in range(1, 10) else '打順不明'
                lineup_slots[i, label].update({k: values[k] for k in SPLIT_FIELDS})
    for e in events:
        i = owner[e['batterId'], e['battingTeam']]
        base = e['preState'].split(':')[1]
        if '1' in base[1:]:
            for month in (None, e['date'][:7]):
                official[i, month]['scoringPositionAtBats'] += int(e['eventType'] in AB)
                official[i, month]['scoringPositionHits'] += int(e['eventType'] in HITS)
        key = (e['gameId'], e['batterId'], e['battingTeam'])
        game_ordinal[key] += 1
        ordinal = game_ordinal[key]
        label = '5打席目以上' if ordinal >= 5 else f'{ordinal}打席目'
        plate_ordinals[i, label].update(event_stats(e))
        expected_plates[(*key, ordinal)] = e
    official_manifest = any('officialEventType' in plate for entry in entries
                            for plate in entry.get('dashboard', {}).get('plateAppearances', []))
    seen_plates = Counter()
    completed_plates = []
    attribute_groups = {split: defaultdict(Counter) for split in
                        ('byPitchType', 'byVelocity', 'byPitcherHand', 'byStrikeCount')}
    unknown_attributes = Counter()
    if official_manifest:
        for entry in entries:
            if not entry['date'].startswith(season):
                continue
            i = owner[entry['batterId'], entry['team']]
            official_box = boxes[entry['gameId']][entry['team']][entry['batterId']]
            compare(i, f'manifestStatline/{entry["gameId"]}', entry['statline'],
                    {field: official_box.get(field, 0)
                     for field in ('ab', 'hits', 'homeRuns', 'rbi', 'walks', 'strikeouts')})
            for plate in entry.get('dashboard', {}).get('plateAppearances', []):
                if plate.get('completed') is False:
                    continue
                key = (entry['gameId'], entry['batterId'], entry['team'], plate.get('paNumber'))
                expected = expected_plates.get(key)
                scope = f'manifest/{entry["gameId"]}/{plate.get("paNumber")}'
                compare(i, scope, {'officialEventExists': int(expected is not None)}, {'officialEventExists': 1})
                if expected is None:
                    continue
                seen_plates[key] += 1
                sparse_counts = plate.get('officialCounts') or {}
                compare(i, scope, {field: sparse_counts.get(field, 0) for field in SPLIT_FIELDS},
                        event_stats(expected))
                compare(i, scope, {'officialEventTypeMatches': int(plate.get('officialEventType') == expected['eventType']),
                                  'scoringPosition': int(bool(plate.get('scoringPosition')))},
                        {'officialEventTypeMatches': 1,
                         'scoringPosition': int('1' in expected['preState'].split(':')[1][1:])})
                completed_plates.append((i, plate, expected))
                attributes = plate.get('splitAttributes') or {}
                speed, strikes = attributes.get('speed'), attributes.get('strikes')
                compare(i, scope, {'validSpeed': int(speed is None or isinstance(speed, (int, float)) and speed > 0),
                                  'validStrikeCount': int(strikes is None or strikes in (0, 1, 2)),
                                  'validPitcherHand': int(attributes.get('pitcherHand') in (None, '', '右', '左'))},
                        {'validSpeed': 1, 'validStrikeCount': 1, 'validPitcherHand': 1})
                labels = {'byPitchType': attributes.get('pitchType') or '球種不明',
                          'byVelocity': ('球速不明' if speed is None else
                                         ('150km/h以上' if speed >= 150 else '150km/h未満')),
                          'byPitcherHand': attributes.get('pitcherHand') or '投手左右不明',
                          'byStrikeCount': 'カウント不明' if strikes is None else f'{strikes}ストライク'}
                for split, label in labels.items():
                    attribute_groups[split][i, label].update(event_stats(expected))
                    if '不明' in label:
                        unknown_attributes[split] += 1
        for key, e in expected_plates.items():
            i = owner[e['batterId'], e['battingTeam']]
            compare(i, f'manifest/{key[0]}/{key[3]}', {'occurrences': seen_plates[key]}, {'occurrences': 1})
    dashboard_rows = 0
    for i, p in enumerate(players):
        for month, row in [(None, p)] + [(m['month'], m) for m in p.get('monthlySplits', [])]:
            expected = dict(official[i, month])
            expected.setdefault('scoringPositionAtBats', 0)
            expected.setdefault('scoringPositionHits', 0)
            compare(i, month or 'annual', row, expected)
            compare(i, month or 'annual', row, rates(row), rate=True)
        dashboard = p.get('seasonDashboard')
        if not dashboard:
            if p['plateAppearances']:
                compare(i, 'seasonDashboard', {}, {'totalPlateAppearances': p['plateAppearances']})
            continue
        dashboard_rows += 1
        compare(i, 'seasonDashboard', dashboard, {'totalPlateAppearances': p['plateAppearances']})
        for recent in dashboard.get('recentGames', []):
            source = boxes[recent['gameId']][recent['team']][p['batterId']]
            expected = {field: source.get(key, 0) for field, key in FIELDS.items()}
            scope = f'recentGames/{recent["gameId"]}'
            compare(i, scope, recent, {field: value for field, value in expected.items() if field in recent})
            compare(i, scope, recent, rates(expected), rate=True)
        for split in SPLITS:
            grouped = dashboard.get(split, [])
            summed = {field: sum(r.get(field, 0) for r in grouped) for field in SPLIT_FIELDS}
            compare(i, f'{split}/total', summed, {field: p.get(field, 0) for field in SPLIT_FIELDS})
            for row in grouped:
                compare(i, f'{split}/{row["label"]}', row, rates(row), rate=True)
            independent_groups = {'byOpponent': opponents, 'byStadium': stadiums,
                                  'byPlateAppearance': plate_ordinals, 'byBattingOrder': lineup_slots}
            if official_manifest:
                independent_groups.update(attribute_groups)
            if split in independent_groups:
                expected_groups = independent_groups[split]
                actual_groups = {r['label']: r for r in grouped}
                labels = set(actual_groups) | {label for (ix, label), values in expected_groups.items()
                                               if ix == i and values['plateAppearances']}
                for label in labels:
                    compare(i, f'{split}/{label}', actual_groups.get(label, {}),
                            {field: expected_groups[i, label][field] for field in SPLIT_FIELDS})
    missing_speed = Counter()
    for entry in entries:
        for plate in entry.get('dashboard', {}).get('plateAppearances', []):
            if not re.search(r'\d', str(plate.get('speed', ''))):
                missing_speed['plateAppearances'] += 1
    historical_rows = 0
    for player in all_players:
        if player['year'] == season:
            continue
        for scope, row in [(f'{player["year"]}/annual', player)] + [
                (m['month'], m) for m in player.get('monthlySplits', [])]:
            historical_rows += 1
            for field, value in rates(row).items():
                if field not in row:
                    continue
                checks['historicalRate'] += 1
                actual = row[field]
                if ((actual is None) != (value is None)
                        or (actual is not None and abs(actual-value) > 0.000501)):
                    differences.append({'player': player['player'], 'batterId': player.get('batterId'),
                                        'team': player['team'], 'scope': scope, 'field': field,
                                        'actual': actual, 'expected': value})
    return {'season': season, 'games': len(dates), 'plateAppearances': len(events),
            'annualRows': len(players), 'dashboardRows': dashboard_rows, 'checks': dict(checks),
            'officialManifestChecked': official_manifest,
            'officialManifestCompletedPlates': len(completed_plates),
            'unknownSplitAttributes': dict(unknown_attributes),
            'historicalRateRowsChecked': historical_rows,
            'missingFinalPitchSpeed': dict(missing_speed),
            'differenceCount': len(differences),
            'affectedPlayers': len({(d['batterId'], d['team']) for d in differences}),
            'differencesByScope': dict(Counter(d['scope'].split('/')[0] for d in differences)),
            'differences': differences}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', default='2026')
    parser.add_argument('--report', type=Path, default=ROOT/'docs/batter-aggregate-audit.json')
    args = parser.parse_args()
    report = audit(args.season)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'differences'}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['differenceCount']))
