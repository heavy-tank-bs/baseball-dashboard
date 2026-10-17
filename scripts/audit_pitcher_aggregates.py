"""Audit every saved pitcher appearance and annual/monthly/conditional aggregate.

Standard-library, read-only audit. Source counting statistics are the saved
game statlines; raw-pitch checks independently exclude incomplete PA results.
This does not claim to authenticate pitch locations or unrecorded IBB pitches.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
GAME_FIELDS = {'batters': 'batters', 'pitches': 'pitches', 'hits': 'hits', 'homeRuns': 'hr',
               'strikeouts': 'k', 'walks': 'bb', 'hitByPitch': 'hbp', 'runs': 'runs', 'earnedRuns': 'er'}
TEAM_NAMES = {'読売ジャイアンツ': '巨人', '阪神タイガース': '阪神', '横浜DeNAベイスターズ': 'DeNA',
              '広島東洋カープ': '広島', '中日ドラゴンズ': '中日', '東京ヤクルトスワローズ': 'ヤクルト',
              '福岡ソフトバンクホークス': 'ソフトバンク', '北海道日本ハムファイターズ': '日本ハム',
              'オリックス・バファローズ': 'オリックス', '東北楽天ゴールデンイーグルス': '東北楽天',
              '埼玉西武ライオンズ': '西武', '千葉ロッテマリーンズ': 'ロッテ', '楽天': '東北楽天'}


def read(name):
    content = (ROOT / 'summary' / name).read_text(encoding='utf-8')
    return json.loads(content[content.index('{'):].rstrip(';\n')) if name.endswith('.js') else json.loads(content)


def integer(value):
    return int(value or 0) if str(value or 0).isdigit() else 0


def outs(value):
    match = re.fullmatch(r'(\d+)(?:\.([012]))?', str(value))
    assert match, f'Unknown innings notation: {value}'
    return int(match[1]) * 3 + int(match[2] or 0)


def classify_terminal(value):
    result = str(value or '').split('[', 1)[0].strip()
    if not result or result in {'ボール', 'ストライク', '見逃し', '空振り', 'ファウル', 'バントファウル'}:
        return 'INCOMPLETE'
    if any(word in result for word in ('盗塁', '盗失', 'けん制', '牽制', '走塁死', '途中終了', '途中交代')):
        return 'INCOMPLETE'
    for terms, category in [(('故意四', '敬遠'), 'IBB'), (('四球',), 'BB'), (('死球',), 'HBP'),
                            (('犠飛',), 'SF'), (('犠打', '犠野', '犠失'), 'SH'), (('打撃妨害', '打妨', '捕妨'), 'INT')]:
        if any(term in result for term in terms):
            return category
    if result.endswith('本'):
        return 'HR'
    if result.endswith(('2', '２')):
        return '2B'
    if result.endswith(('3', '３')):
        return '3B'
    if '安' in result:
        return '1B'
    if '三振' in result or '振逃' in result:
        return 'K'
    if any(word in result for word in ('ゴロ', '併打', '飛', '直', 'ライナー', '失', '野選', 'アウト', '守備妨害')):
        return 'OUT'
    return 'UNKNOWN'


def pitch_bucket():
    return Counter()


def add_pitch(bucket, row):
    bucket['count'] += 1
    result = str(row.get('result') or '').split('[', 1)[0].strip()
    speed = re.fullmatch(r'(\d+(?:\.\d+)?)\s*km/h', str(row.get('speed') or ''))
    if speed:
        value = float(speed[1])
        bucket['speedCount'] += 1
        bucket['speedTotal'] += value
        bucket['maxSpeed'] = max(bucket['maxSpeed'], value)
    whiff = any(term in result for term in ('空振り', '空三振', 'バ三振', '振逃'))
    called = '見逃し' in result or '見三振' in result or result == 'ストライク'
    ball = any(term in result for term in ('ボール', '四球', '死球', '故意四', '敬遠'))
    contact = bool(result) and not whiff and not called and not ball
    swing = whiff or contact
    bucket['whiffCount'] += int(whiff)
    bucket['calledStrikeCount'] += int(called)
    bucket['swingCount'] += int(swing)
    if row.get('left') is not None and row.get('top') is not None:
        bucket['locatedCount'] += 1
        zone = 54.0 * 0.2 <= float(row['left']) <= 54.0 * 0.8 and 63.0 * 0.2 <= float(row['top']) <= 63.0 * 0.8
        bucket['zoneCount' if zone else 'outZoneCount'] += 1
        bucket['zoneSwingCount' if zone else 'outZoneSwingCount'] += int(swing)
        if not zone:
            bucket['outZoneContactCount'] += int(contact)


def add_terminal(bucket, category):
    bucket['atBats'] += int(category in {'1B', '2B', '3B', 'HR', 'K', 'OUT'})
    mapping = {'1B': 'singles', '2B': 'doubles', '3B': 'triples', 'HR': 'homeRuns', 'K': 'strikeouts', 'SF': 'sacrificeFlies'}
    if category in mapping:
        bucket[mapping[category]] += 1


def audit(report_path, inspect=False):
    entries = read('manifest.js')['entries']
    totals = read('player_totals.json')
    players = [p for p in totals['players'] if p['year'] == '2026']
    decisions = read('game_decisions_cache.json')['games']
    contexts = {g['gameId']: g for g in read('sportsnavi_game_context_2026.json')['games']}
    if inspect:
        sample = next(p for p in players if p.get('seasonDashboard'))
        entry = next(e for e in entries if e['pitcherId'] == sample['pitcherId'])
        raw = json.loads((ROOT / 'generated' / entry['team'] / entry['date'] / f'{entry["prefix"]}-dashboard.json').read_text(encoding='utf-8'))
        detail = json.loads((ROOT / 'summary' / entry['detailPath']).read_text(encoding='utf-8'))['dashboard']
        print(json.dumps({'annualKeys': list(sample), 'seasonDashboard': sample['seasonDashboard'],
                          'rawKeys': list(raw), 'pitchSample': raw['pitches'][:2],
                          'detailKeys': list(detail), 'countMix': detail.get('countMix')}, ensure_ascii=False, indent=2))
        return
    row_for = {}
    for index, player in enumerate(players):
        for team in player.get('sourceTeams') or player['teams']:
            assert (player['pitcherId'], team) not in row_for
            row_for[(player['pitcherId'], team)] = index
    findings = defaultdict(lambda: {'count': 0, 'players': set(), 'examples': []})
    checks = Counter()
    def check(category, owner, field, actual, expected, detail='', tolerance=0):
        checks[category] += 1
        equal = actual == expected
        if not equal and actual is not None and expected is not None and isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            equal = abs(actual - expected) <= tolerance
        if not equal:
            issue = findings[category + ':' + field]
            issue['count'] += 1
            issue['players'].add(players[owner]['pitcherId'])
            if len(issue['examples']) < 12:
                issue['examples'].append({'player': players[owner]['player'], 'pitcherId': players[owner]['pitcherId'],
                                          'detail': detail, 'actual': actual, 'expected': expected})
    expected_annual, expected_monthly = defaultdict(Counter), defaultdict(Counter)
    coverage_by_owner, coverage_by_month = defaultdict(Counter), defaultdict(Counter)
    split_counts = defaultdict(Counter)
    outcomes_by_owner = defaultdict(Counter)
    missing_source_games = []
    pitch_groups = defaultdict(lambda: defaultdict(pitch_bucket))
    raw_terminals, unknown, incomplete = Counter(), Counter(), []
    unknown_innings = []
    total_raw, appearances = 0, set()
    for index, entry in enumerate(entries):
        if not entry['date'].startswith('2026'):
            continue
        owner = row_for[(entry['pitcherId'], entry['team'])]
        identity = (entry['gameId'], entry['team'], entry['pitcherId'])
        assert identity not in appearances
        appearances.add(identity)
        monthly_key = owner, entry['date'][:7]
        stats = entry['statline']
        expected = Counter(games=1, inningsOuts=outs(stats['innings']))
        expected.update({field: integer(stats[source]) for field, source in GAME_FIELDS.items()})
        game_decisions = decisions[entry['gameId']]
        decision = game_decisions.get(entry['pitcherId'])
        if decision is None:
            decision = next((d for d in game_decisions.values() if d.get('player') == entry.get('player')), {})
        expected.update({field: integer(decision.get(field)) for field in ('wins', 'losses', 'saves', 'holds')})
        expected_annual[owner].update(expected)
        expected_monthly[monthly_key].update(expected)
        context = contexts.get(entry['gameId'], {})
        teams = [TEAM_NAMES.get(context.get(key), context.get(key)) for key in ('homeTeam', 'awayTeam')]
        opponent = next((t for t in teams if t and t != entry['team']), '-')
        for group, label in [('opponentRows', opponent), ('stadiumRows', context.get('stadium') or '-')]:
            split_counts[(owner, group, label)].update(expected)
        raw_path = ROOT / 'generated' / entry['team'] / entry['date'] / f'{entry["prefix"]}-dashboard.json'
        raw = json.loads(raw_path.read_text(encoding='utf-8'))
        rows = raw.get('pitches') or []
        detail = json.loads((ROOT / 'summary' / entry['detailPath']).read_text(encoding='utf-8'))['dashboard']
        total_raw += len(rows)
        check('rawPitchCount', owner, 'pitches', len(rows), integer(stats['pitches']), entry['id'])
        check('rawPitchIdentity', owner, 'uniquePitchNumbers', len({p['pitchNo'] for p in rows}), len(rows), entry['id'])
        for field, source in GAME_FIELDS.items():
            check('rawStatline', owner, field, integer(raw['statline'].get(source)), expected[field], entry['id'])
        check('gameDashboard', owner, 'totalPitches', detail.get('totalPitches'), len(rows), entry['id'])
        pa = defaultdict(list)
        for row in rows:
            pa[row.get('pa_index')].append(row)
            prefix = str(row.get('pa_index'))[:2]
            inning = int(prefix) if prefix.isdigit() else None
            if inning is None and len(unknown_innings) < 20:
                unknown_innings.append({'entry': entry['id'], 'pitch': row})
            for category, label in [('pitchMix', row.get('pitchType') or '-'), ('batterHandRows', row.get('batter_hand') or '-'), ('inningRows', inning)]:
                add_pitch(pitch_groups[(owner, category)][label], row)
        game_terminal = Counter()
        game_outcomes = Counter()
        count_mix = defaultdict(Counter)
        for pa_key, pitches in pa.items():
            ordered = sorted(pitches, key=lambda p: integer(p.get('seq')))
            balls, strikes, previous, known = 0, 0, 0, True
            for pitch in ordered:
                seq = integer(pitch.get('seq'))
                known = known and seq == previous + 1
                previous = seq
                label = ('不明' if not known else '初球' if seq == 1 or (balls == 0 and strikes == 0)
                         else 'フルカウント' if (balls, strikes) == (3, 2)
                         else '2ストライク以降' if strikes == 2 else '追い込み前')
                count_mix[label][pitch.get('pitchType') or '-'] += 1
                result = str(pitch.get('result') or '')
                if any(word in result for word in ('ボール', '四球', '死球')):
                    balls = min(3, balls + 1)
                elif 'ファウル' in result:
                    strikes = min(2, strikes + 1)
                elif any(word in result for word in ('見逃し', '空振り', '見三振', '空三振', 'ストライク')):
                    strikes = min(2, strikes + 1)
            final = max(pitches, key=lambda p: integer(p.get('seq')))
            category = classify_terminal(final.get('result'))
            raw_terminals[category] += 1
            game_terminal[category] += 1
            primary = str(final.get('result') or '').split('[', 1)[0].strip()
            outcome = ('lookingStrikeouts' if '見' in primary else 'swingingStrikeouts') if category == 'K' else (
                'sacrificeBunts' if category == 'SH' else 'interference' if '守備妨害' in primary else
                'grounders' if any(w in primary for w in ('ゴロ', '併打')) else
                'flyballs' if any(w in primary for w in ('飛', '直', 'ライナー')) else None)
            if outcome:
                game_outcomes[outcome] += 1
            if category == 'UNKNOWN':
                unknown[str(final.get('result'))] += 1
            if category == 'INCOMPLETE' and len(incomplete) < 40:
                incomplete.append({'entry': entry['id'], 'paIndex': pa_key, 'result': final.get('result')})
            prefix = str(pa_key)[:2]
            for group, label in [('pitchMix', final.get('pitchType') or '-'), ('batterHandRows', final.get('batter_hand') or '-'), ('inningRows', int(prefix) if prefix.isdigit() else None)]:
                add_terminal(pitch_groups[(owner, group)][label], category)
        for field, value in [('hits', sum(game_terminal[k] for k in ('1B', '2B', '3B', 'HR'))), ('homeRuns', game_terminal['HR']), ('strikeouts', game_terminal['K']), ('hitByPitch', game_terminal['HBP'])]:
            check('rawTerminalVsStatline', owner, field, value, expected[field], entry['id'])
        complete = (len(rows) == expected['pitches'] and not game_terminal['UNKNOWN']
                    and sum(game_terminal[k] for k in ('1B', '2B', '3B', 'HR')) == expected['hits']
                    and game_terminal['HR'] == expected['homeRuns'] and game_terminal['K'] == expected['strikeouts']
                    and game_terminal['HBP'] == expected['hitByPitch'])
        game_coverage = Counter(games=1, incompleteGames=int(not complete), unknownGames=0,
                               recordedPitches=len(rows), officialPitches=expected['pitches'],
                               unknownInningPitches=sum(not str(p.get('pa_index'))[:2].isdigit() for p in rows))
        coverage_by_owner[owner].update(game_coverage)
        coverage_by_month[monthly_key].update(game_coverage)
        if not complete:
            missing_source_games.append({'entry': entry['id'], 'recordedPitches': len(rows), 'officialPitches': expected['pitches'],
                                         'recordedTerminals': dict(game_terminal)})
        check('sourceCoverage', owner, 'gameComplete', (detail.get('sourceCoverage') or {}).get('complete'), complete, entry['id'])
        outcomes_by_owner[owner].update(game_outcomes)
        for outcome_row in (detail.get('outcomes') or {}).get('rows', []):
            check('outcomes', owner, outcome_row['id'], outcome_row['count'], game_outcomes[outcome_row['id']], entry['id'])
        for count_row in detail.get('countMix', []):
            label = count_row['bucket']
            check('countMix', owner, 'total', count_row['total'], sum(count_mix[label].values()), entry['id'] + ':' + label)
            for segment in count_row['segments']:
                count = count_mix[label][segment['pitchType'] or '-']
                check('countMix', owner, 'count', segment['count'], count, entry['id'] + ':' + label)
                ratio = round(count / count_row['total'] * 100, 1) if count_row['total'] else 0.0
                check('countMix', owner, 'ratio', segment['ratio'], ratio, entry['id'] + ':' + label)
        check('countMix', owner, 'partition', sum(r['total'] for r in detail.get('countMix', [])), len(rows), entry['id'])
        finish = detail.get('finish') or {}
        check('finish', owner, 'strikeouts', finish.get('total'), game_terminal['K'], entry['id'])
        check('finish', owner, 'partition', sum(r['count'] for r in finish.get('rows', [])), game_terminal['K'], entry['id'])
        for finish_row in finish.get('rows', []):
            check('finish', owner, 'lookingSwinging', finish_row['looking'] + finish_row['swinging'], finish_row['count'], entry['id'])
        if (index + 1) % 1000 == 0:
            print(f'Audited {index + 1}/{len(entries)} appearances', flush=True)
    for owner, player in enumerate(players):
        for field, expected in expected_annual[owner].items():
            check('annualOfficialCounts', owner, field, player.get(field), expected)
        for month in player.get('monthlySplits', []):
            for field, expected in expected_monthly[(owner, month['month'])].items():
                check('monthlyOfficialCounts', owner, field, month.get(field), expected, month['month'])
        for item, expected_coverage in [(player, coverage_by_owner[owner])] + [(m, coverage_by_month[(owner, m['month'])]) for m in player.get('monthlySplits', [])]:
            label = item.get('month', 'annual')
            for field, value in expected_coverage.items():
                check('sourceCoverage', owner, field, (item.get('sourceCoverage') or {}).get(field), value, label)
            ip = item['inningsOuts'] / 3
            for field, numerator, denominator, digits in [
                ('era', item['earnedRuns'] * 9, ip, 2), ('whip', item['hits'] + item['walks'], ip, 2),
                ('kPer9', item['strikeouts'] * 27, item['inningsOuts'], 2), ('bbPer9', item['walks'] * 27, item['inningsOuts'], 2),
                ('hPer9', item['hits'] * 27, item['inningsOuts'], 2), ('hrPer9', item['homeRuns'] * 27, item['inningsOuts'], 2),
                ('kBb', item['strikeouts'], item['walks'], 2)]:
                check('derivedRates', owner, field, item.get(field), round(numerator / denominator, digits) if denominator else None, label)
            check('derivedRates', owner, 'uBB', item['unintentionalWalks'], item['walks'] - item['intentionalWalks'], label)
            fip = (((13 * item['homeRuns'] + 3 * (item['unintentionalWalks'] + item['hitByPitch']) - 2 * item['strikeouts']) / ip)
                   + item['fipConstant']) if ip and item.get('fipConstant') is not None else None
            # Published constants have four decimals, so allow their rounding interval.
            check('derivedRates', owner, 'fip', item.get('fip'), round(fip, 2) if fip is not None else None, label, 0.010001)
            for field, numerator, denominator in [
                ('battingAverageAllowed', item['hits'], item['atBats']),
                ('babipAllowed', item['hits'] - item['homeRuns'], item['atBats'] - item['strikeouts'] - item['homeRuns'] + item['sacrificeFlies'])]:
                target = round(numerator / denominator, 3) if denominator > 0 and not expected_coverage['incompleteGames'] else None
                check('derivedRates', owner, field, item.get(field), target, label)
        dashboard = player.get('seasonDashboard') or {}
        total = sum(b['count'] for b in pitch_groups[(owner, 'pitchMix')].values())
        check('seasonDashboard', owner, 'totalPitches', dashboard.get('totalPitches'), total)
        check('sourceCoverage', owner, 'seasonDashboard', dashboard.get('sourceCoverage'), dict(coverage_by_owner[owner]))
        for outcome_row in (dashboard.get('outcomes') or {}).get('rows', []):
            check('seasonOutcomes', owner, outcome_row['id'], outcome_row['count'], outcomes_by_owner[owner][outcome_row['id']])
        for group in ('opponentRows', 'stadiumRows'):
            for split in dashboard.get(group, []):
                for field, value in split_counts[(owner, group, split['label'])].items():
                    if field not in ('wins', 'losses', 'saves', 'holds'):
                        check('gameSplit:' + group, owner, field, split.get(field), value, split['label'])
            for field in ('games', 'inningsOuts', 'batters', 'pitches', 'hits', 'homeRuns', 'strikeouts', 'walks', 'hitByPitch', 'runs', 'earnedRuns'):
                check('gameSplitPartition', owner, field, sum(r.get(field, 0) for r in dashboard.get(group, [])), player[field], group)
        for group, label_key in [('pitchMix', 'pitchType'), ('batterHandRows', 'label'), ('inningRows', 'inning')]:
            for actual in dashboard.get(group, []):
                label = actual[label_key]
                expected = pitch_groups[(owner, group)][label]
                for field in ('count', 'speedCount', 'speedTotal', 'whiffCount', 'swingCount', 'calledStrikeCount',
                              'locatedCount', 'zoneCount', 'outZoneCount', 'zoneSwingCount', 'outZoneSwingCount', 'outZoneContactCount',
                              'atBats', 'singles', 'doubles', 'triples', 'homeRuns', 'strikeouts', 'sacrificeFlies'):
                    target = expected[field]
                    if field == 'speedTotal' and not expected['speedCount']:
                        target = None
                    check('source:' + group, owner, field, actual.get(field), target, str(label), 0.100001 if field == 'speedTotal' else 0)
                ratios = {'whiff': ('whiffCount', 'count', 100, 1), 'whiffRate': ('whiffCount', 'swingCount', 100, 1),
                          'zoneRate': ('zoneCount', 'locatedCount', 100, 1), 'zSwing': ('zoneSwingCount', 'zoneCount', 100, 1),
                          'chase': ('outZoneSwingCount', 'outZoneCount', 100, 1), 'oContact': ('outZoneContactCount', 'outZoneSwingCount', 100, 1)}
                for field, (numerator, denominator, factor, digits) in ratios.items():
                    target = round(expected[numerator] / expected[denominator] * factor, digits) if expected[denominator] else None
                    check('sourceRates:' + group, owner, field, actual.get(field), target, str(label))
                hits = sum(expected[k] for k in ('singles', 'doubles', 'triples', 'homeRuns'))
                target = round(hits / expected['atBats'], 3) if expected['atBats'] else None
                check('sourceRates:' + group, owner, 'hitRate', actual.get('hitRate'), target, str(label))
    report = {'scope': '2026 saved pitcher source and aggregate audit', 'annualRows': len(players),
              'uniquePitchers': len({p['pitcherId'] for p in players}), 'appearances': len(appearances),
              'rawPitches': total_raw, 'checks': dict(checks), 'rawTerminalCategories': dict(raw_terminals),
              'unknownTerminalResults': dict(unknown), 'incompletePASamples': incomplete,
              'unknownInningSamples': unknown_innings, 'sourceIncompleteAppearances': missing_source_games,
              'findings': {key: {**value, 'players': sorted(value['players'])} for key, value in findings.items()},
              'limitations': ['Saved game statlines are the counting-stat baseline; their full external box-score verification is recorded separately in pitcher-official-audit.json.',
                              'Raw pitch locations and velocities are source observations, not independently measured values.',
                              'Intentional walks can have no pitch row; official context is needed for complete BB/PA accounting.',
                              'Inning runs assigned proportionally by the builder are estimates, not verified pitcher responsibility per inning.',
                              'Inning walk rows count observed pitch-ending BB/HBP only; unpitched IBB and missing PA cannot be reconstructed by inning.',
                              'Pitch-type/hand/inning rates describe recorded pitches and PA only; incomplete source coverage is carried in sourceCoverage.',
                              'Count states after a missing initial pitch or a sequence gap are explicitly unknown, not assumed 0-0.',
                              '2025 has no full raw pitch corpus here and is excluded from source reconstruction.']}
    source_findings = {k: v for k, v in report['findings'].items()
                       if k.startswith(('rawPitchCount:', 'rawTerminalVsStatline:'))}
    aggregate_findings = {k: v for k, v in report['findings'].items() if k not in source_findings}
    report['aggregateDifferenceCount'] = sum(v['count'] for v in aggregate_findings.values())
    report['sourceDifferenceCount'] = sum(v['count'] for v in source_findings.values())
    report['status'] = 'passed-with-source-limitations' if not aggregate_findings else 'failed'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'findings', 'incompletePASamples', 'unknownInningSamples', 'sourceIncompleteAppearances'}}, ensure_ascii=False, indent=2))
    print(json.dumps({key: value['count'] for key, value in report['findings'].items()}, ensure_ascii=False, indent=2))
    if aggregate_findings:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/pitcher-aggregate-audit.json')
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    audit(args.report, args.inspect)
