"""Collect and cache the last two 2026 regular-season games from Sports Navi.

Fetch each play once, then reuse it for every pitcher. Cached HTML is temporary
and lives under .site-build; permanent outputs live under generated.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import time
from types import SimpleNamespace
from datetime import datetime

from rebuild_annual_totals import load_builder
import fetch_sportsnavi_game_context as context_builder
import build_woba_constants as woba

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.site-build/final-games'
GAMES = {'2021051134': '2026-10-07', '2021051699': '2026-10-08'}
SKILL = ROOT / 'scripts/build_dashboard.py'


def builder():
    spec = importlib.util.spec_from_file_location('dashboard', SKILL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (re.sub(r'[^a-zA-Z0-9_-]', '_', url.split('/npb/')[-1]) + '.html')
    if path.exists():
        return path.read_text(encoding='utf-8')
    for attempt in range(3):
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=45)
        if response.ok:
            path.write_text(response.text, encoding='utf-8')
            return response.text
        time.sleep(attempt + 1)
    response.raise_for_status()


def normalize_output_directories(module):
    """Repair full-name output folders from older collection runs, without overwrite."""
    root = (ROOT / 'generated').resolve()
    for name in ('阪神タイガース', '広島東洋カープ', '東京ヤクルトスワローズ'):
        source = (root / name).resolve()
        assert source.parent == root
        if not source.exists():
            continue
        for date_dir in source.iterdir():
            if not date_dir.is_dir() or date_dir.name not in GAMES.values():
                raise ValueError(f'Unexpected output directory: {date_dir}')
            destination = (root / module.normalize_matchup_team_name(name) / date_dir.name).resolve()
            assert destination.is_relative_to(root)
            destination.mkdir(parents=True, exist_ok=True)
            for path in date_dir.iterdir():
                if not path.is_file() or path.name.split('-')[0] not in GAMES:
                    raise ValueError(f'Unexpected generated file: {path}')
                target = destination / path.name
                if target.exists():
                    if target.read_bytes() != path.read_bytes():
                        raise ValueError(f'Conflicting output: {target}')
                    path.unlink()
                else:
                    path.rename(target)
            date_dir.rmdir()
        source.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--skip-png', action='store_true')
    args = parser.parse_args()
    module = builder()
    manifest_builder = load_builder()
    normalize_output_directories(manifest_builder)
    context_path = ROOT / 'summary/sportsnavi_game_context_2026.json'
    context = json.loads(context_path.read_text(encoding='utf-8'))
    new_contexts = []
    new_events = []
    for game_id, date in GAMES.items():
        stats_html = fetch(f'https://baseball.yahoo.co.jp/npb/game/{game_id}/stats')
        score_html = fetch(f'https://baseball.yahoo.co.jp/npb/game/{game_id}/score')
        if args.probe:
            page = module.parse_score_page_html(score_html, None)
            soup = BeautifulSoup(score_html, 'html.parser')
            print(game_id, 'stats', len(stats_html), 'score', len(score_html), 'last page', page, flush=True)
            for i, table in enumerate(soup.select('#pitchesDetail table')):
                print('table', i, table.get('class'), table.get_text(' ', strip=True)[:500], flush=True)
            previous_html = fetch(f'https://baseball.yahoo.co.jp/npb/game/{game_id}/score?index={page["prev"]}')
            print('previous', module.parse_score_page_html(previous_html, page['prev']), flush=True)
            continue
        pages_path = CACHE / f'{game_id}-pages.json'
        if pages_path.exists():
            pages = json.loads(pages_path.read_text(encoding='utf-8'))
        else:
            pages, seen, index = [], set(), None
            while True:
                html = score_html if index is None else fetch(f'https://baseball.yahoo.co.jp/npb/game/{game_id}/score?index={index}')
                page = module.parse_score_page_html(html, index)
                pages.append(page)
                previous = page['prev']
                if not previous:
                    break
                if previous in seen:
                    raise ValueError(f'Navigation loop at {game_id} {previous}')
                seen.add(previous)
                index = previous
                if len(pages) % 20 == 0:
                    print(game_id, 'fetched play pages', len(pages), flush=True)
            pages_path.write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
        ids = {p['matchup']['pitcher_id'] for p in pages if p['pitch_rows']}
        soup = BeautifulSoup(stats_html, 'html.parser')
        official_ids = set()
        for table in soup.select('table'):
            headers = [module.text(th) for th in table.select('thead th')]
            if '投球回' in headers and '投球数' in headers:
                official_ids.update(re.search(r'/player/(\d+)/', a['href']).group(1) for a in table.select('a[href*="/npb/player/"]'))
        if ids != official_ids:
            raise ValueError(f'Pitcher coverage mismatch: {ids ^ official_ids}')
        cached_session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(text=stats_html, raise_for_status=lambda: None))
        for player_id in sorted(ids):
            pitches = module.collect_pitcher_rows(pages, None, player_id)
            statline, metadata = module.parse_statline(cached_session, game_id, None, player_id)
            if len(pitches) != int(statline['pitches']):
                raise ValueError(f'Pitch count mismatch: {game_id} {statline["player"]} {len(pitches)} != {statline["pitches"]}')
            if any(p['left'] is None or p['top'] is None for p in pitches):
                raise ValueError(f'Missing pitch locations: {game_id} {player_id}')
            home, away = metadata['matchup'].split('vs')
            team = home if pitches[0]['pa_index'][2] == '1' else away
            team = manifest_builder.normalize_matchup_team_name(team)
            output = ROOT / 'generated' / team / date
            output.mkdir(parents=True, exist_ok=True)
            prefix = module.sanitize_filename(f'{game_id}-{statline["player"]}')
            payload = {'game_id': game_id, 'metadata': metadata, 'statline': statline, 'pitches': pitches}
            (output / f'{prefix}-dashboard.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            summary = output / f'{prefix}-summary.txt'
            if args.skip_png:
                module.write_dashboard_summary(payload, summary)
            elif not all((output / f'{prefix}-dashboard-{i}.png').exists() for i in range(1, 5)):
                module.render_dashboard(payload, *(output / f'{prefix}-dashboard-{i}.png' for i in range(1, 5)), summary)
            print(game_id, team, statline['player'], len(pitches), 'pitches verified', flush=True)
        batting = manifest_builder.load_game_batting_cache()
        batting['games'][game_id] = manifest_builder.parse_game_batting_stats_from_html(stats_html)
        batting.setdefault('sources', {})[game_id] = f'https://baseball.yahoo.co.jp/npb/game/{game_id}/stats'
        manifest_builder.save_game_batting_cache(batting)
        decisions = manifest_builder.load_game_decisions_cache()
        decisions['games'][game_id] = manifest_builder.parse_game_decisions_from_html(stats_html)
        manifest_builder.save_game_decisions_cache(decisions)
        schedule = fetch(context_builder.SCHEDULE_URL.format(date=date))
        matches = [g for g in context_builder.parse_schedule_page(schedule, date) if g['gameId'] == game_id]
        if len(matches) != 1 or matches[0]['status'] != '試合終了':
            raise ValueError(f'Completed schedule row missing for {game_id}')
        game = matches[0]
        walks = context_builder.parse_intentional_walks_from_stats(stats_html)
        game['intentionalWalks'] = {'total': sum(t['intentionalWalks'] for t in walks.values()), 'teams': walks}
        game['inningScores'] = context_builder.parse_inning_scores_from_stats(stats_html)
        new_contexts.append(game)
        events = woba.parse_game_text(game, fetch(woba.TEXT_URL.format(game_id=game_id)))
        expected_pa = sum(r['plateAppearances'] for rows in batting['games'][game_id].values() for key, r in rows.items() if key == r['playerId'])
        if len(events) != expected_pa:
            counts = {}
            for event in events:
                counts[event['batterId']] = counts.get(event['batterId'], 0) + 1
            for rows in batting['games'][game_id].values():
                for key, row in rows.items():
                    if key == row['playerId'] and counts.get(key, 0) != row['plateAppearances']:
                        print('PA discrepancy', row, [e for e in events if e['batterId'] == key], flush=True)
            raise ValueError(f'Event coverage mismatch {game_id}: {len(events)} != {expected_pa}')
        new_events.extend(events)
    if args.probe:
        return
    context['games'] = sorted([g for g in context['games'] if g['gameId'] not in GAMES] + new_contexts, key=lambda g: (g['date'], g['gameId']))
    context['updatedAt'] = datetime.now().astimezone().isoformat(timespec='seconds')
    context['throughDate'] = max(GAMES.values())
    summary = context['summary']
    summary['completedGames'] = len(context['games'])
    summary['scheduledGames'] = summary['completedGames'] + summary['canceledGames'] + summary['otherStatusGames']
    summary['statusCounts']['試合終了'] = summary['completedGames']
    summary['gamesWithIntentionalWalks'] = sum(g['intentionalWalks']['total'] > 0 for g in context['games'])
    summary['intentionalWalkPlateAppearances'] = sum(g['intentionalWalks']['total'] for g in context['games'])
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    events_path = ROOT / 'summary/sportsnavi_woba_events_2026.json'
    events_payload = json.loads(events_path.read_text(encoding='utf-8'))
    events_payload['events'] = [e for e in events_payload['events'] if str(e['gameId']) not in GAMES] + new_events
    events_payload['eventCount'] = len(events_payload['events'])
    events_payload['updatedAt'] = context['updatedAt']
    events_path.write_text(json.dumps(events_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    constants_path = ROOT / 'summary/woba_constants.json'
    constants = json.loads(constants_path.read_text(encoding='utf-8'))
    year = woba.calculate_constants_for_year('2026', events_payload['events'])
    old_year = constants['byYear']['2026']
    year.update(games=len({e['gameId'] for e in events_payload['events']}), parsedPlateAppearances=len(events_payload['events']), fetchErrors=[e for e in old_year.get('fetchErrors', []) if str(e.get('gameId')) not in GAMES])
    constants['byYear']['2026'] = year
    constants['updatedAt'] = context['updatedAt']
    constants_path.write_text(json.dumps(constants, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Final game context and wOBA events saved', flush=True)


if __name__ == '__main__':
    main()
