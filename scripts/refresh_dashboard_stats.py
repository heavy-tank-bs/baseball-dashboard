"""Refresh stats for saved games. Use --source npb after audit_dashboard.py.

Successful games are checkpointed. Failed responses never replace cached data.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from rebuild_annual_totals import ROOT, load_builder, read_manifest


def valid_batting(value):
    return isinstance(value, dict) and len(value) == 2 and all(
        isinstance(rows, dict) and rows and all(isinstance(row, dict) and 'plateAppearances' in row for row in rows.values())
        for rows in value.values()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['sportsnavi', 'npb'], default='sportsnavi')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    m = load_builder()
    entries = read_manifest('manifest.js')
    decisions = m.load_game_decisions_cache()
    batting = m.load_game_batting_cache()
    dg, bg = decisions.setdefault('games', {}), batting.setdefault('games', {})
    stale = decisions.get('decisionParserVersion') != m.GAME_DECISION_CACHE_VERSION
    ids = sorted({e['gameId'] for e in entries if stale or not valid_batting(bg.get(e['gameId'])) or not isinstance(dg.get(e['gameId']), dict) or not dg.get(e['gameId'])})
    urls, lookup, display_names = {}, {}, {}
    if args.source == 'npb':
        from npb_boxscore_stats import parse_boxscore, normalize_name
        games = json.loads((ROOT / '.site-build/audit/official-games.json').read_text(encoding='utf-8'))
        urls = {game['gameId']: game['url'] + 'box.html' for game in games if game.get('gameId')}
        for field, rows in [('pitcherId', entries), ('batterId', read_manifest('batter_manifest.js'))]:
            for row in rows:
                if row.get(field):
                    lookup[(row['team'], normalize_name(row['player']))] = row[field]
                    display_names[row[field]] = row['player']
        for name, field in [('player_totals.json', 'pitcherId'), ('batter_totals.json', 'batterId')]:
            for row in json.loads((ROOT / 'summary' / name).read_text(encoding='utf-8'))['players']:
                if row.get(field):
                    display_names.setdefault(row[field], row['player'])
                    for team in row.get('teams') or [row['team']]:
                        lookup.setdefault((team, normalize_name(row['player'])), row[field])
        by_name = {}
        for (_, name), player_id in lookup.items():
            by_name.setdefault(name, set()).add(player_id)
        for name, values in by_name.items():
            if len(values) == 1:
                lookup[('', name)] = next(iter(values))
        from bs4 import BeautifulSoup
        import re
        roster_cache = ROOT / '.site-build/npb-player-map.json'
        if roster_cache.exists() and json.loads(roster_cache.read_text(encoding='utf-8')):
            npb_names = json.loads(roster_cache.read_text(encoding='utf-8'))
        else:
            def roster(url):
                response = requests.get(url, headers=m.REQUEST_HEADERS, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                return {re.search(r'/players/(\d+)\.html', a['href'])[1]: a.get_text(' ', strip=True) for a in soup.select('a[href]') if re.search(r'/players/(\d+)\.html', a['href'])}
            roster_urls = [f'https://npb.jp/bis/teams/rst_{code}.html' for code in ['g','t','db','c','s','d','h','f','m','b','l','e']]
            npb_names = {}
            with ThreadPoolExecutor(max_workers=4) as pool:
                for found in pool.map(roster, roster_urls):
                    npb_names.update(found)
            roster_cache.write_text(json.dumps(npb_names,ensure_ascii=False,indent=2),encoding='utf-8')
        aliases = {'安田悠馬': 'YG安田'}
        for npb_id, name in npb_names.items():
            normalized = normalize_name(name)
            normalized = normalize_name(aliases.get(normalized, normalized))
            player_id = lookup.get(('', normalized))
            if player_id:
                lookup[('npb', npb_id)] = player_id
                lookup[('npb_name', npb_id)] = display_names[player_id]
        print('Official player identities mapped:', sum(k[0]=='npb' for k in lookup), flush=True)

    def fetch(gid):
        for attempt in range(2):
            try:
                url = urls[gid] if args.source == 'npb' else m.SPORTSNAVI_GAME_STATS_URL.format(game_id=gid)
                response = requests.get(url, headers=m.REQUEST_HEADERS, timeout=35)
                response.raise_for_status()
                response.encoding = 'utf-8'
                if args.source == 'npb':
                    b, d = parse_boxscore(response.text, lookup)
                else:
                    b, d = m.parse_game_batting_stats_from_html(response.text), m.parse_game_decisions_from_html(response.text)
                if not valid_batting(b):
                    raise ValueError('Expected complete batting tables for two teams')
                if not d:
                    raise ValueError('Missing pitcher decisions')
                return gid, b, d
            except Exception:
                if attempt:
                    raise
                time.sleep(2)

    def save():
        if not stale or all(gid in refreshed for gid in ids):
            decisions['decisionParserVersion'] = m.GAME_DECISION_CACHE_VERSION
        m.save_game_decisions_cache(decisions)
        m.save_game_batting_cache(batting)

    errors, refreshed = [], set()
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
        jobs = {pool.submit(fetch, gid): gid for gid in ids}
        for i, future in enumerate(as_completed(jobs), 1):
            try:
                gid, b, d = future.result()
                bg[gid], dg[gid] = b, d
                refreshed.add(gid)
                batting.setdefault('sources', {})[gid] = args.source
            except Exception as exc:
                errors.append({'gameId': jobs[future], 'error': str(exc)})
                if len(errors) <= 5:
                    print('Fetch error:', errors[-1], flush=True)
            if i % 50 == 0:
                save()
                print(f'{i}/{len(ids)} processed; errors={len(errors)}', flush=True)
    save()
    report = ROOT / '.site-build/stats-fetch-errors.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Finished: {len(refreshed)} refreshed; {len(errors)} errors', flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
