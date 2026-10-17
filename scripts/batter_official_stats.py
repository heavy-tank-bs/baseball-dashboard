"""Attach official completed PAs while retaining every observed pitch for discipline."""
from collections import defaultdict
import json
from pathlib import Path

from batter_event_ledger import build_ledger, audit_counts


def compact_provenance(entries):
    """Keep original values only when they differ from the displayed values."""
    for entry in entries:
        for plate in entry['dashboard']['plateAppearances']:
            if plate.get('originalResult') == plate.get('result'):
                plate.pop('originalResult', None)
            if plate.get('originalScoringPosition') == plate.get('scoringPosition'):
                plate.pop('originalScoringPosition', None)


def enrich_entries(entries, batting, builder):
    by_game = defaultdict(list)
    for entry in entries:
        entry['dashboard']['plateAppearances'] = [
            p for p in entry['dashboard']['plateAppearances']
            if not (str(p.get('id', '')).startswith('official-') and not p.get('points'))]
        by_game[str(entry['gameId'])].append(entry)
    events = []
    for year in sorted({entry['date'][:4] for entry in entries}):
        path = builder.SUMMARY_DIR / f'sportsnavi_woba_events_{year}.json'
        if not path.exists():
            raise ValueError(f'Official PA ledger required: {path}')
        events.extend(e for e in json.loads(path.read_text(encoding='utf-8'))['events']
                      if str(e['gameId']) in by_game)
    records, report = build_ledger(entries, events)
    check = audit_counts(records, batting)
    if check['differences']:
        raise ValueError(f'Official PA/box score mismatch: {check["differences"][:5]}')
    report['officialCountAudit'] = check
    index = {(str(e['gameId']), e['team'], str(e['batterId'])): e for e in entries}
    for entry in entries:
        for plate in entry['dashboard']['plateAppearances']:
            plate.setdefault('originalScoringPosition', bool(plate.get('scoringPosition')))
            plate['completed'] = False
            plate['scoringPosition'] = None
            plate['label'] = '参考投球（打席集計外）'
    for record in records:
        key = str(record['gameId']), record['battingTeam'], str(record['batterId'])
        entry = index.get(key)
        if entry is None:
            game = by_game[key[0]][0]
            stats = batting[key[0]][key[1]][key[2]]
            date, player = record['date'], stats['player']
            entry = {
                'id': f'{key[1]}-{date}-{key[0]}-{key[2]}', 'team': key[1],
                'league': builder.team_league(key[1]), 'date': date,
                'prefix': f'{key[0]}-{key[2]}', 'gameId': key[0], 'title': player,
                'player': player, 'batterId': key[2], 'uniformNumber': '', 'batterHand': '',
                'matchup': game['matchup'], 'dateLabel': game['dateLabel'],
                'order': stats.get('order', 999), 'battingOrder': stats.get('battingOrder'),
                'isStarter': stats.get('isStarter'),
                'statline': {f: stats[f] for f in ('ab', 'hits', 'homeRuns', 'rbi', 'walks', 'strikeouts')},
                'dashboard': {'pitchMix': [], 'pitchColors': {}, 'plateAppearances': [],
                              'bounds': {'width': builder.HEATMAP_WIDTH, 'height': builder.HEATMAP_HEIGHT}},
            }
            entries.append(entry)
            index[key] = entry
        plate = record['logPlate']
        if plate is None:
            plate = {'id': f'official-{record["paNumber"]}', 'points': [],
                     'inning': record['inning'], **record['attributes']}
            entry['dashboard']['plateAppearances'].append(plate)
        elif 'originalResult' not in plate:
            plate['originalResult'] = plate.get('result')
        plate.update(completed=True, officialEventType=record['eventType'],
                     officialCounts={key: value for key, value in record['counts'].items() if value}, paNumber=record['paNumber'],
                     matchStatus=record['matchStatus'], scoringPosition=record['scoringPosition'],
                     result=record['result'], label=f'{record["paNumber"]}打席目')
        # Only uniquely matched attributes can enter conditional statistics.
        plate['splitAttributes'] = {key: record['attributes'][key]
                                    for key in ('pitchType', 'speed', 'pitcherHand', 'strikes')}
    for entry in entries:
        entry['dashboard']['plateAppearances'].sort(
            key=lambda p: (p.get('paNumber', 999), str(p.get('id', ''))))
    builder.write_text_atomic(builder.ROOT / 'docs/batter-ledger-verification.json',
                              json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    compact_provenance(entries)
    return entries


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact-manifest', action='store_true', required=True)
    parser.parse_args()
    path = Path(__file__).resolve().parent.parent / 'summary/batter_manifest.js'
    text = path.read_text(encoding='utf-8')
    start = text.index('{')
    payload = json.loads(text[start:].rstrip(';\n'))
    compact_provenance(payload['entries'])
    path.write_text(text[:start] + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    print('Compacted manifest bytes:', path.stat().st_size)
