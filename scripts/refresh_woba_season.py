"""Fetch, audit, and publish wOBA inputs for every regular-season game.

HTML caches are resumable under .site-build/woba-npb-source. Published files are
only replaced after every expected game passes the official-stat audit.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import gzip
import json
from pathlib import Path
import time
import threading
import re

import requests

import build_woba_constants as woba

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.site-build/woba-source'
STOP_FETCH = threading.Event()
FETCH_SOURCE = 'direct'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def inputs(season):
    content = (ROOT / 'summary/manifest.js').read_text(encoding='utf-8')
    entries = json.loads(content[content.index('{'):].rstrip(';\n'))['entries']
    ids = {e['gameId'] for e in entries if e['date'].startswith(season)}
    contexts = read_json(ROOT / f'summary/sportsnavi_game_context_{season}.json')
    games = {g['gameId']: g for g in contexts['games'] if g['gameId'] in ids}
    assert set(games) == ids, 'Missing regular-season game context'
    batting = read_json(ROOT / 'summary/game_batting_cache.json')['games']
    assert ids <= batting.keys(), 'Missing official batting cache'
    return sorted(games.values(), key=lambda g: (g['date'], g['gameId'])), batting


def fetch(game):
    path = CACHE / f'{game["gameId"]}.html.gz'
    if path.exists():
        return game['gameId'], 'cached'
    if STOP_FETCH.is_set():
        return game['gameId'], 'deferred after upstream errors'
    error = None
    for attempt in range(3):
        try:
            url = woba.TEXT_URL.format(game_id=game['gameId'])
            headers = dict(woba.REQUEST_HEADERS)
            if FETCH_SOURCE == 'npb':
                url = game['playbyplayUrl']
            if FETCH_SOURCE == 'jina':
                url = 'https://r.jina.ai/' + url
                headers.update({'X-Respond-With': 'html', 'X-Respond-Timing': 'html', 'Accept': 'application/json'})
            response = requests.get(url, headers=headers, timeout=120 if FETCH_SOURCE == 'jina' else 30)
            if not response.ok:
                raise RuntimeError(f'HTTP {response.status_code}: {response.text[:180]}')
            html = response.json()['data']['content'] if FETCH_SOURCE == 'jina' else response.content.decode('utf-8')
            marker = 'id="com1-1"' if FETCH_SOURCE == 'npb' else 'bb-liveText__inning'
            if marker not in html:
                raise ValueError('No completed-game text sections')
            path.write_bytes(gzip.compress(html.encode('utf-8')))
            return game['gameId'], 'fetched'
        except Exception as exc:
            error = exc
            time.sleep(1 + attempt)
    return game['gameId'], str(error)


def npb_lookup(batting):
    from bs4 import BeautifulSoup
    from npb_boxscore_stats import normalize_name
    lookup, names, by_name = {}, {}, defaultdict(set)
    for teams in batting.values():
        for team, rows in teams.items():
            for key, row in rows.items():
                if key != row['playerId']:
                    continue
                normalized = normalize_name(row['player'])
                lookup[(team, normalized)] = key
                names[key] = row['player']
                by_name[normalized].add(key)
    for name, ids in by_name.items():
        if len(ids) == 1:
            lookup[('', name)] = next(iter(ids))
    roster_path = CACHE.parent / 'npb-player-map.json'
    if roster_path.exists():
        roster_names = read_json(roster_path)
    else:
        def roster(code):
            response = requests.get(f'https://npb.jp/bis/teams/rst_{code}.html', timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
            return {re.search(r'/players/(\d+)\.html', a['href'])[1]: a.get_text(' ', strip=True)
                    for a in soup.select('a[href]') if re.search(r'/players/(\d+)\.html', a['href'])}
        roster_names = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for found in pool.map(roster, ('g','t','db','c','s','d','h','f','m','b','l','e')):
                roster_names.update(found)
        roster_path.write_text(json.dumps(roster_names, ensure_ascii=False, indent=2), encoding='utf-8')
    for npb_id, name in roster_names.items():
        normalized = normalize_name(name)
        normalized = {'安田悠馬': 'YG安田'}.get(normalized, normalized)
        player_id = lookup.get(('', normalized))
        lookup[('npb_name', npb_id)] = names.get(player_id, name)
        if player_id:
            lookup[('npb', npb_id)] = player_id
    return lookup


def audit(game, events, batting):
    errors = []
    for team, players in batting.items():
        subset = [e for e in events if e['battingTeam'] == team]
        per_player = defaultdict(Counter)
        for event in subset:
            per_player[event['batterId']][event['eventType']] += 1
        expected = Counter()
        expected_pa = Counter()
        for key, row in players.items():
            if key != row['playerId']:
                continue
            expected_pa[key] += row['plateAppearances']
            for field in ('plateAppearances', 'runs', 'hits', 'walks', 'hitByPitch', 'sacBunts', 'homeRuns', 'doubles', 'triples', 'singles'):
                expected[field] += row[field]
            count = per_player[key]
            actual_player = {'ab': sum(count[k] for k in ('1B','2B','3B','HR','OUT','ROE')),
                             'singles': count['1B'], 'doubles': count['2B'], 'triples': count['3B'],
                             'homeRuns': count['HR'], 'walks': count['uBB'] + count['IBB'],
                             'hitByPitch': count['HBP'], 'sacBunts': count['SH']}
            differences = {field: {'expected': row[field], 'actual': value}
                           for field, value in actual_player.items() if row[field] != value}
            if differences:
                errors.append({'team': team, 'kind': 'playerEvents', 'playerId': key, 'player': row['player'], 'differences': differences})
        actual_pa = Counter(e['batterId'] for e in subset)
        if +expected_pa != +actual_pa:
            errors.append({'team': team, 'kind': 'playerPA', 'expected': dict(+expected_pa), 'actual': dict(actual_pa)})
        counts = Counter(e['eventType'] for e in subset)
        actual = {'plateAppearances': len(subset), 'hits': sum(counts[k] for k in ('1B','2B','3B','HR')),
                  'walks': counts['uBB'] + counts['IBB'], 'hitByPitch': counts['HBP'], 'sacBunts': counts['SH'],
                  'homeRuns': counts['HR'], 'doubles': counts['2B'], 'triples': counts['3B'], 'singles': counts['1B']}
        for field, value in actual.items():
            if value != expected[field]:
                errors.append({'team': team, 'kind': field, 'expected': expected[field], 'actual': value})
        innings = {(e['inning'], e['half']): e['inningRuns'] for e in subset}
        if sum(innings.values()) != expected['runs']:
            errors.append({'team': team, 'kind': 'runs', 'expected': expected['runs'], 'actual': sum(innings.values())})
        unknown = [e for e in subset if e['eventType'] == 'OTHER']
        if unknown:
            errors.append({'team': team, 'kind': 'unknownEvents', 'events': unknown})
    return errors


def main():
    global FETCH_SOURCE, CACHE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', default='2026')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--source', choices=('direct', 'jina', 'npb'), default='npb')
    parser.add_argument('--game-id', action='append', help='Fetch/audit only selected IDs; never publish a partial season')
    parser.add_argument('--fetch-only', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--audit-cached', action='store_true', help='Audit available HTML only; never publish a partial season')
    args = parser.parse_args()
    FETCH_SOURCE = args.source
    if FETCH_SOURCE == 'npb':
        CACHE = ROOT / '.site-build/woba-npb-source'
    games, batting = inputs(args.season)
    if FETCH_SOURCE == 'npb':
        official = read_json(ROOT / '.site-build/audit/official-games.json')
        urls = {g['gameId']: g['url'] + 'playbyplay.html' for g in official}
        assert {g['gameId'] for g in games} <= urls.keys(), 'Run audit_dashboard.py to map every official game URL'
        games = [dict(g, playbyplayUrl=urls[g['gameId']]) for g in games]
    expected_games = len(games)
    if args.game_id:
        games = [g for g in games if g['gameId'] in args.game_id]
    if args.audit_cached:
        games = [g for g in games if (CACHE / f'{g["gameId"]}.html.gz').exists()]
    CACHE.mkdir(parents=True, exist_ok=True)
    failures = []
    if not args.audit_only and not args.audit_cached:
        with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
            futures = [pool.submit(fetch, game) for game in games]
            for index, future in enumerate(as_completed(futures), 1):
                game_id, status = future.result()
                if status not in ('cached', 'fetched'):
                    failures.append({'gameId': game_id, 'error': status})
                    if len(failures) <= 3:
                        print(failures[-1], flush=True)
                    if len(failures) >= 8:
                        STOP_FETCH.set()
                if index % 25 == 0 or index == len(games):
                    print(f'Fetched/cached {index}/{len(games)}, errors={len(failures)}', flush=True)
                    (CACHE.parent / 'woba-fetch-errors.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
        (CACHE.parent / 'woba-fetch-errors.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
        if failures:
            raise SystemExit(f'{len(failures)} fetch failures; rerun to resume')
    if args.fetch_only:
        return
    lookup = npb_lookup(batting) if FETCH_SOURCE == 'npb' else None
    if FETCH_SOURCE == 'npb':
        from npb_woba_events import parse_game_text as parse_npb_game
    all_events, audits = [], []
    for game in games:
        html = gzip.decompress((CACHE / f'{game["gameId"]}.html.gz').read_bytes()).decode('utf-8')
        try:
            events = parse_npb_game(game, html, lookup) if FETCH_SOURCE == 'npb' else woba.parse_game_text(game, html)
        except Exception as exc:
            audits.append({'gameId': game['gameId'], 'date': game['date'], 'errors': [{'kind': 'parseError', 'error': str(exc)}]})
            continue
        errors = audit(game, events, batting[game['gameId']])
        if errors:
            audits.append({'gameId': game['gameId'], 'date': game['date'], 'errors': errors})
        all_events.extend(events)
    report = {'expectedGames': expected_games, 'parsedGames': len({e['gameId'] for e in all_events}),
              'plateAppearances': len(all_events), 'failedGames': len(audits), 'errors': audits}
    (CACHE.parent / 'woba-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print({key: value for key, value in report.items() if key != 'errors'}, flush=True)
    print('Audit mismatch types:', dict(Counter(e['kind'] for g in audits for e in g['errors'])), flush=True)
    if audits:
        print('Audit details: .site-build/woba-audit.json', flush=True)
        raise SystemExit(1)
    if args.audit_only or args.audit_cached or args.game_id:
        return
    report['officialPlateAppearances'] = sum(row['plateAppearances'] for game in games
        for rows in batting[game['gameId']].values() for key, row in rows.items() if key == row['playerId'])
    report['allOfficialCountsMatch'] = True
    report['source'] = 'NPB official play-by-play' if FETCH_SOURCE == 'npb' else 'Sports Navi game text pages'
    report['gameIds'] = [g['gameId'] for g in games]
    report['eventCounts'] = dict(sorted(Counter(e['eventType'] for e in all_events).items()))
    team_counts = defaultdict(Counter)
    for game in games:
        for team in batting[game['gameId']]:
            team_counts[team]['games'] += 1
    for event in all_events:
        team_counts[event['battingTeam']]['plateAppearances'] += 1
    report['teams'] = dict(team_counts)
    constants = woba.calculate_constants_for_year(args.season, all_events)
    if FETCH_SOURCE == 'npb':
        constants['source'] = f'NPB official play-by-play, {len(games)} regular-season games through {games[-1]["date"]}'
    constants.update(games=len(games), expectedGames=len(games), coverageComplete=True,
                     parsedPlateAppearances=len(all_events), fetchErrors=[])
    constants['eventParser'] = 'npb-official-v1' if FETCH_SOURCE == 'npb' else f'sportsnavi-v{woba.PARSER_VERSION}'
    assert len(constants['stateSampleCounts']) == 24 and not constants['missingRunValueCounts'], 'Incomplete RE24 inputs'
    timestamp = datetime.now().astimezone().isoformat(timespec='seconds')
    payload = read_json(woba.CONSTANTS_PATH)
    payload['byYear'][args.season] = constants
    payload['updatedAt'] = timestamp
    payload['source'] = 'NPB official play-by-play' if FETCH_SOURCE == 'npb' else 'Sports Navi game text pages'
    if FETCH_SOURCE == 'npb':
        payload['notes'] = {
            'scope': 'Independent provisional wOBA constants from all regular-season games, excluding All-Star and postseason games.',
            'scale': 'Raw linear weights are shifted by average OUT value and scaled to league OBP with IBB removed.',
            'limitations': 'Independently computed, not official NPB constants. RE24 uses plate-appearance states without per-game park adjustment. Inning/game-ending plays use an absorbing zero-future-runs state; walkoffs are identified separately.',
            'methodology': 'https://library.fangraphs.com/principles/linear-weights/',
            'gameSources': 'https://npb.jp/scores/2026/MMDD/TEAM-TEAM-N/playbyplay.html',
        }
    events_payload = {'updatedAt': timestamp, 'season': args.season, 'gameCount': len(games),
                      'source': payload['source'], 'eventParser': constants['eventParser'], 'eventCount': len(all_events), 'events': all_events}
    for path, data in [(woba.CONSTANTS_PATH, payload), (ROOT / f'summary/sportsnavi_woba_events_{args.season}.json', events_payload),
                       (ROOT / f'docs/woba-coverage-{args.season}.json', report)]:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Published complete season wOBA inputs and constants', flush=True)


if __name__ == '__main__':
    main()
