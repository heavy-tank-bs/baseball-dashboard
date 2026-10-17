"""Join verified official batting events to observed pitch-log attributes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
AB_EVENTS = {'1B', '2B', '3B', 'HR', 'OUT', 'ROE'}
EVENT_TYPES = AB_EVENTS | {'uBB', 'IBB', 'HBP', 'SH', 'SF', 'INT'}
COUNT_FIELDS = ('plateAppearances', 'atBats', 'hits', 'singles', 'doubles', 'triples',
                'homeRuns', 'walks', 'unintentionalWalks', 'intentionalWalks',
                'hitByPitch', 'sacBunts', 'sacFlies', 'strikeouts', 'interference')


def event_counts(event):
    """Official event -> one PA's counting stats, including strikeouts."""
    kind = event['eventType']
    if kind not in EVENT_TYPES:
        raise ValueError(f'Unrecognized official event {kind!r}')
    result = event.get('result') or ''
    strikeout = any(token in result for token in ('三振', '振り逃げ', '振逃'))
    if strikeout and kind != 'OUT':
        raise ValueError(f'Strikeout is not an OUT event: {event}')
    counts = dict.fromkeys(COUNT_FIELDS, 0)
    counts.update(plateAppearances=1, atBats=int(kind in AB_EVENTS), hits=int(kind in {'1B','2B','3B','HR'}),
                  singles=int(kind == '1B'), doubles=int(kind == '2B'), triples=int(kind == '3B'),
                  homeRuns=int(kind == 'HR'), walks=int(kind in {'uBB','IBB'}),
                  unintentionalWalks=int(kind == 'uBB'), intentionalWalks=int(kind == 'IBB'),
                  hitByPitch=int(kind == 'HBP'), sacBunts=int(kind == 'SH'), sacFlies=int(kind == 'SF'),
                  strikeouts=int(strikeout), interference=int(kind == 'INT'))
    return counts


def log_event_type(result):
    """Recognize completed pitch-log PA results; pitch-only outcomes are None."""
    value = unicodedata.normalize('NFKC', (result or '').split('[', 1)[0].strip())
    if any(term in value for term in ('途中終了', '途中交代')):
        return None
    if any(term in value for term in ('申告敬遠', '敬遠', '故意四')):
        return 'IBB'
    if '四球' in value or 'フォアボール' in value:
        return 'uBB'
    if '死球' in value or 'デッドボール' in value:
        return 'HBP'
    if '打妨' in value or '打撃妨害' in value:
        return 'INT'
    if '犠打' in value or '犠牲バント' in value or '犠野' in value:
        return 'SH'
    if '犠飛' in value or '犠牲フライ' in value:
        return 'SF'
    if value.endswith('本') or 'ホームラン' in value:
        return 'HR'
    if re.search(r'[左右中遊一二三投捕]3$', value) or 'スリーベース' in value:
        return '3B'
    if re.search(r'[左右中遊一二三投捕]2$', value) or 'ツーベース' in value:
        return '2B'
    if '安' in value or 'ヒット' in value:
        return '1B'
    if any(term in value for term in ('三振', '振逃', '振り逃げ', '野選', 'フィルダースチョイス')):
        return 'OUT'
    if any(term in value for term in ('失', 'エラー', '悪送球')) and not any(term in value for term in ('盗塁', '牽制')):
        return 'ROE'
    if re.fullmatch(r'[左右中遊一二三投捕](?:ゴロ|飛|邪飛|邪直|直|併打|併殺打|ライナー|フライ|バントゴロ)', value) or value in {'守備妨害', '走塁妨害アウト'}:
        return 'OUT'
    return None


def _half_key(entry, plate):
    identifier = str(plate.get('id') or '')
    if not re.match(r'^\d{2}[12]', identifier):
        return None
    return str(entry['gameId']), entry['team'], int(identifier[:2]), '表' if identifier[2] == '1' else '裏'


def _event_half_key(event):
    return str(event['gameId']), event['battingTeam'], int(event['inning']), event['half']


def _best_alignment(left, right, forbidden=None):
    table = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) - 1, -1, -1):
        for j in range(len(right) - 1, -1, -1):
            score = max(table[i+1][j], table[i][j+1])
            if left[i] == right[j] and forbidden != (i, j):
                score = max(score, 1 + table[i+1][j+1])
            table[i][j] = score
    return table


def _forced_pairs(left, right):
    """Only identity/order pairings present in every maximal monotone match."""
    if left == right:
        return {i: i for i in range(len(left))}
    best = _best_alignment(left, right)[0][0]
    if not best:
        return {}
    return {i: j for i in range(len(left)) for j in range(len(right))
            if left[i] == right[j] and _best_alignment(left, right, (i, j))[0][0] < best}


def _attributes(plate):
    result = dict.fromkeys(('pitchType', 'speed', 'pitcher', 'pitcherHand', 'balls', 'strikes', 'batterHand', 'pitchNo'))
    if plate is None:
        return result
    for name in ('pitchType', 'pitcher', 'pitcherHand', 'batterHand'):
        value = plate.get(name)
        result[name] = value if value and value != '-' else None
    raw = plate.get('speed')
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(?:km/h)?', str(raw or ''))
    if match and math.isfinite(float(match[1])) and float(match[1]) > 0:
        result['speed'] = float(match[1])
    for name, maximum in (('balls', 3), ('strikes', 2), ('pitchNo', 999)):
        value = plate.get(name)
        if isinstance(value, int) and 0 <= value <= maximum:
            result[name] = value
    return result


def _original_result(plate):
    return plate.get('originalResult', plate.get('result'))


def _original_risp(plate):
    return bool(plate.get('originalScoringPosition', plate.get('scoringPosition')))


def build_ledger(batter_entries, official_events):
    """Return (records, report), preserving official chronology and identities.

    Records contain original official fields plus `paNumber`, `counts`,
    `scoringPosition`, `plate`/`logPlate`, `attributes`, and `matchStatus`.
    Official IBB has no pitch attribution. Incomplete pitch-log turns never
    become a PA. Ambiguous alignments retain official counts with unknown pitch
    attributes, rather than shifting a later PA into the missing slot.
    """
    records, groups = [], defaultdict(list)
    per_player_order = Counter()
    for event in official_events:
        key = str(event['gameId']), event['battingTeam'], str(event['batterId'])
        per_player_order[key] += 1
        state = event.get('preState') or ''
        if not re.fullmatch(r'[012]:[01]{3}', state):
            raise ValueError(f'Invalid official preState: {state!r}')
        record = dict(event, paNumber=per_player_order[key], counts=event_counts(event),
                      scoringPosition=state[-2:] != '00', plate=None, logPlate=None,
                      attributes=_attributes(None), matchStatus='official-only')
        if event['eventType'] == 'IBB':
            record['matchStatus'] = 'intentional-walk-no-pitch'
        else:
            groups[_event_half_key(event)].append(len(records))
        records.append(record)
    observed, log_rows, ignored = defaultdict(list), [], []
    event_game_ids = {str(e['gameId']) for e in official_events}
    for entry in batter_entries:
        if str(entry['gameId']) not in event_game_ids:
            continue
        for plate in (entry.get('dashboard') or {}).get('plateAppearances') or []:
            if str(plate.get('id') or '').startswith('official-') and not plate.get('points'):
                # These are ledger-generated records, not independent pitch
                # observations. Never use them to corroborate themselves.
                continue
            kind = log_event_type(_original_result(plate))
            key = _half_key(entry, plate)
            row = {'gameId': str(entry['gameId']), 'team': entry['team'], 'batterId': str(entry['batterId']),
                   'plate': plate, 'eventType': kind, 'entryId': entry['id']}
            if not kind or key is None or kind == 'IBB':
                row['reason'] = 'intentional-walk-log' if kind == 'IBB' else 'non-completed-or-unrecognized' if not kind else 'unknown-inning-half'
                ignored.append(row)
                continue
            row['index'] = len(log_rows)
            log_rows.append(row)
            observed[key].append(row)
    matched, corrections, risp_differences = set(), [], []
    for key, official_indices in groups.items():
        logs = sorted(observed.get(key, []), key=lambda row: (int(row['plate']['id']), row['batterId']))
        left = [str(records[index]['batterId']) for index in official_indices]
        right = [row['batterId'] for row in logs]
        pairs = _forced_pairs(left, right)
        for official_index, log_index in pairs.items():
            record, source = records[official_indices[official_index]], logs[log_index]
            plate = source['plate']
            record.update(plate=plate, logPlate=plate, attributes=_attributes(plate), matchStatus='matched')
            matched.add(source['index'])
            if record['eventType'] != source['eventType']:
                record['matchStatus'] = 'matched-official-result-corrected'
                corrections.append({'gameId': record['gameId'], 'team': record['battingTeam'], 'batterId': record['batterId'],
                                    'paNumber': record['paNumber'], 'official': record['eventType'], 'log': source['eventType'],
                                    'officialResult': record['result'], 'logResult': _original_result(plate)})
            if _original_risp(plate) != record['scoringPosition']:
                risp_differences.append({'gameId': record['gameId'], 'team': record['battingTeam'], 'batterId': record['batterId'],
                                        'paNumber': record['paNumber'], 'official': record['scoringPosition'],
                                        'log': _original_risp(plate)})
        for index in official_indices:
            if records[index]['plate'] is None and logs:
                records[index]['matchStatus'] = 'unmatched-or-ambiguous'
    compact = lambda row: {k: row[k] for k in ('gameId','team','batterId','eventType','entryId')} | {'id': row['plate'].get('id'), 'result': _original_result(row['plate'])}
    report = {'officialGames': len(event_game_ids), 'officialPlateAppearances': len(records),
              'observedCompletedPlateAppearances': len(log_rows), 'matchedPlateAppearances': len(matched),
              'matchStatusCounts': dict(Counter(row['matchStatus'] for row in records)),
              'ignoredLogCount': len(ignored), 'ignoredLogReasons': dict(Counter(row['reason'] for row in ignored)),
              'ignoredLogResults': dict(Counter(_original_result(row['plate']) for row in ignored)),
              'unmatchedCompletedLogCount': len(log_rows) - len(matched),
              'unmatchedCompletedLogs': [compact(row) for row in log_rows if row['index'] not in matched],
              'resultCorrectionCount': len(corrections), 'resultCorrections': corrections,
              'rispCorrectionCount': len(risp_differences), 'rispCorrections': risp_differences,
              'unmatchedOfficialEvents': [{k: row[k] for k in ('gameId','battingTeam','batterId','inning','half','paNumber','eventType','result','matchStatus')}
                                         for row in records if row['plate'] is None and row['eventType'] != 'IBB'],
              'unknownAttributeCounts': {name: sum(row['attributes'][name] is None for row in records)
                                         for name in _attributes(None)}}
    return records, report


def audit_counts(records, batting_games):
    actual = defaultdict(Counter)
    for record in records:
        actual[(record['gameId'], record['battingTeam'], str(record['batterId']))].update(record['counts'])
    fields = {'plateAppearances': 'plateAppearances', 'atBats': 'ab', 'hits': 'hits', 'singles': 'singles',
              'doubles': 'doubles', 'triples': 'triples', 'homeRuns': 'homeRuns', 'walks': 'walks',
              'hitByPitch': 'hitByPitch', 'sacBunts': 'sacBunts', 'sacFlies': 'sacFlies', 'strikeouts': 'strikeouts'}
    game_ids = {row['gameId'] for row in records}
    differences, checked = [], set()
    for game_id in game_ids:
        for team, players in batting_games[game_id].items():
            for player_id, player in players.items():
                if player_id != player['playerId']:
                    continue
                key = (game_id, team, player_id)
                checked.add(key)
                for field, source_field in fields.items():
                    if actual[key][field] != player[source_field]:
                        differences.append({'gameId': game_id, 'team': team, 'batterId': player_id, 'field': field,
                                            'officialCache': player[source_field], 'ledger': actual[key][field]})
    for key in actual.keys() - checked:
        differences.append({'gameId': key[0], 'team': key[1], 'batterId': key[2], 'field': 'unexpected-player'})
    return {'checkedPlayerGames': len(checked), 'fields': list(fields), 'differences': differences}


def read_manifest(path):
    value = path.read_text(encoding='utf-8')
    return json.loads(value[value.index('{'):].rstrip(';\n'))['entries']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--season', default='2026')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--verify-enrichment', action='store_true', help='Verify enrichment twice in memory; never write manifests')
    args = parser.parse_args()
    entries = read_manifest(ROOT / 'summary/batter_manifest.js')
    if args.inspect:
        print(json.dumps(entries[0], ensure_ascii=False, indent=2)[:14000])
        return
    events = json.loads((ROOT / f'summary/sportsnavi_woba_events_{args.season}.json').read_text(encoding='utf-8'))['events']
    records, report = build_ledger(entries, events)
    batting = json.loads((ROOT / 'summary/game_batting_cache.json').read_text(encoding='utf-8'))['games']
    report['officialCountAudit'] = audit_counts(records, batting)
    if args.verify_enrichment:
        from types import SimpleNamespace
        from batter_official_stats import enrich_entries
        teams = {entry['team']: entry['league'] for entry in entries}
        builder = SimpleNamespace(ROOT=ROOT, SUMMARY_DIR=ROOT / 'summary', HEATMAP_WIDTH=54.0, HEATMAP_HEIGHT=63.0,
                                  team_league=teams.get, write_text_atomic=lambda path, content: None)
        def signatures(rows):
            return [(r['gameId'], r['battingTeam'], r['batterId'], r['paNumber'],
                     (r['plate'] or {}).get('id'), r['matchStatus'], r['attributes'], r['counts']) for r in rows]
        previous = signatures(records)
        counts = []
        for attempt in range(2):
            enrich_entries(entries, batting, builder)
            repeated, repeated_report = build_ledger(entries, events)
            if signatures(repeated) != previous:
                raise AssertionError(f'Ledger matches changed after enrichment pass {attempt + 1}')
            if repeated_report != {key: value for key, value in report.items() if key != 'officialCountAudit'}:
                raise AssertionError(f'Ledger report changed after enrichment pass {attempt + 1}')
            counts.append(sum(len(e['dashboard']['plateAppearances']) for e in entries))
        if counts[0] != counts[1]:
            raise AssertionError(f'Enrichment duplicated plate rows: {counts}')
        report['enrichmentReplay'] = {'passes': 2, 'plateRowsAfterEachPass': counts, 'allMatchesUnchanged': True, 'allReportsUnchanged': True}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if not isinstance(value, list) and key != 'officialCountAudit'}, ensure_ascii=False, indent=2))
    print('Official count discrepancies:', len(report['officialCountAudit']['differences']))
    if report['officialCountAudit']['differences']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
