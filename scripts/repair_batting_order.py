"""Recover actual lineup slots from every official box score, then repair splits.

Only published batting-order metadata and batting-order splits are changed.
The local cache also gains missing official SF counts. Cached HTML is resumable;
no published file is updated until all official rows reconcile.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import gzip
import json
from pathlib import Path
import time
import subprocess

import requests
from npb_boxscore_stats import parse_boxscore
from refresh_woba_season import npb_lookup
from rebuild_annual_totals import load_builder, read_manifest

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.site-build/batting-order'
FIELDS = ('ab', 'hits', 'homeRuns', 'walks', 'hitByPitch', 'plateAppearances',
          'doubles', 'triples', 'singles', 'sacBunts', 'sacFlies', 'strikeouts')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--audit-cached', action='store_true', help='Inspect cached HTML without publishing')
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    games = read(ROOT / '.site-build/audit/official-games.json')
    entries = read_manifest('batter_manifest.js')
    assert len(games) == 858 and {g['gameId'] for g in games} == {e['gameId'] for e in entries}
    cache_path = ROOT / 'summary/game_batting_cache.json'
    batting = read(cache_path)
    # The box-score parser also validates pitching totals, including DH-game
    # pitchers who never have a batting-cache row.
    identity_rows = {}
    for entry in read_manifest('manifest.js'):
        identity_rows.setdefault(entry['team'], {})[entry['pitcherId']] = {
            'playerId': entry['pitcherId'], 'player': entry['player']}
    lookup = npb_lookup({**batting['games'], '_pitcher_identities': identity_rows})
    if args.audit_cached:
        games = [g for g in games if (CACHE / f'{g["gameId"]}.html.gz').exists()]

    def fetch(game):
        path = CACHE / f'{game["gameId"]}.html.gz'
        for attempt in range(3):
            try:
                if not path.exists():
                    response = requests.get(game['url'] + 'box.html', timeout=35)
                    response.raise_for_status()
                    path.write_bytes(gzip.compress(response.content))
                parsed, _ = parse_boxscore(gzip.decompress(path.read_bytes()).decode('utf-8'), lookup)
                return game['gameId'], parsed
            except Exception:
                if attempt == 2 or args.audit_cached:
                    raise
                time.sleep(1 + attempt)
    results, errors = {}, []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
        futures = {pool.submit(fetch, game): game['gameId'] for game in games}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                game_id, parsed = future.result()
                results[game_id] = parsed
            except Exception as exc:
                errors.append({'gameId': futures[future], 'error': str(exc)})
                if len(errors) <= 5:
                    print(errors[-1], flush=True)
            if i % 50 == 0 or i == len(games):
                print(f'Official box scores {i}/{len(games)}, errors={len(errors)}', flush=True)
    if errors:
        (CACHE / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit(f'Failed games: {errors[:5]}')
    if args.audit_cached:
        return

    changes, checked = [], 0
    for game_id, teams in results.items():
        for team, rows in teams.items():
            expected_ids = {key for key, row in batting['games'][game_id][team].items() if key == row['playerId']}
            assert expected_ids == {key for key, row in rows.items() if key == row['playerId']}
            for player_id in expected_ids:
                current, official = batting['games'][game_id][team][player_id], rows[player_id]
                mismatches = {field: (current.get(field), official[field]) for field in FIELDS
                              if field in current and current[field] != official[field]}
                assert not mismatches, f'Counting-stat mismatch: {game_id} {team} {player_id} {mismatches}'
                # Legacy SportsNavi caches did not store SF explicitly. Match
                # its independently implied value before adding that input.
                implied_sf = current['plateAppearances'] - sum(current[k] for k in ('ab','walks','hitByPitch','sacBunts'))
                if 'sacFlies' not in current:
                    # Catcher's interference is also a non-AB PA; the parsed
                    # official box score distinguishes it from sacrifice flies.
                    assert 0 <= official['sacFlies'] <= implied_sf
                assert official['battingOrder'] in range(1, 10)
                checked += 1
                if current['order'] != official['battingOrder']:
                    changes.append({'gameId': game_id, 'team': team, 'playerId': player_id,
                                    'player': current['player'], 'displayRow': current['order'],
                                    'battingOrder': official['battingOrder'], 'isStarter': official['isStarter']})
                # Alias rows share a player ID but are separate after JSON loading.
                for row in batting['games'][game_id][team].values():
                    if row['playerId'] == player_id:
                        row.update(battingOrder=official['battingOrder'], isStarter=official['isStarter'])
                        row.setdefault('sacFlies', official['sacFlies'])
    for entry in entries:
        official = batting['games'][entry['gameId']][entry['team']][entry['batterId']]
        entry.update(battingOrder=official['battingOrder'], isStarter=official['isStarter'])

    m = load_builder()
    game_dates = {entry['gameId']: entry['date'] for entry in entries}
    affiliations = [{'date': game_dates[gid], 'team': team, 'batterId': key}
                    for gid in game_dates for team, rows in batting['games'][gid].items()
                    for key, row in rows.items() if key == row['playerId']]
    m.configure_annual_affiliations(affiliations, 'batterId')
    splits = m.build_batter_order_splits(entries, batting['games'])
    totals_path = ROOT / 'summary/batter_totals.json'
    totals = read(totals_path)
    baseline = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    original = json.loads(subprocess.check_output(['git', 'show', 'HEAD:summary/batter_totals.json'], cwd=ROOT))
    previous = {row['aggregationKey']: row for row in original['players'] if row['year'] == '2026'}
    before_sato, after_sato = None, None
    affected = 0
    for row in totals['players']:
        if row['year'] != '2026':
            continue
        key = (row['year'], row['aggregationKey'])
        updated = splits.get(key, [])
        dashboard = row.get('seasonDashboard')
        if dashboard is None:
            assert not updated
            continue
        if row['batterId'] == '2000051':
            before_sato, after_sato = previous[row['aggregationKey']]['seasonDashboard']['byBattingOrder'], updated
        affected += previous[row['aggregationKey']]['seasonDashboard']['byBattingOrder'] != updated
        dashboard['byBattingOrder'] = updated
    assert after_sato, 'Sato batting-order verification is missing'
    timestamp = datetime.now().astimezone().isoformat(timespec='seconds')
    totals['updatedAt'] = timestamp
    totals.setdefault('notes', {})['battingOrder'] = 'Batting-order splits use official lineup slots and box-score counting stats. Substitutes inherit the replaced lineup slot; display row order is never a lineup slot.'
    batting['battingOrderParserVersion'] = 1
    report = {'baselineCommit': baseline, 'gamesVerified': len(results), 'playerGameRowsVerified': checked,
              'rowsWhoseDisplayIndexDiffersFromLineupSlot': len(changes),
              'annualPlayersCorrected': affected, 'allOfficialCountsPreserved': True,
              'satoBefore': before_sato, 'satoAfter': after_sato,
              'satoGames': [{k: e[k] for k in ('gameId','date','order','battingOrder','isStarter')}
                            for e in entries if e['batterId'] == '2000051'],
              'source': 'NPB official box scores', 'changes': sorted(changes, key=lambda r: (r['gameId'],r['team'],r['displayRow']))}
    cache_path.write_text(json.dumps(batting, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    m.write_text_atomic(m.BATTER_MANIFEST_PATH, 'window.BATTER_GAME_MANIFEST = ' + m.dumps_compact(m.build_manifest(entries)) + ';\n')
    totals_path.write_text(json.dumps(totals, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'docs/batting-order-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k,v in report.items() if k not in ('changes','satoGames','satoBefore')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
