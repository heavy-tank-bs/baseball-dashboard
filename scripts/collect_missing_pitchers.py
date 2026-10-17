"""Collect pitcher appearances absent from the full official pitching audit."""
import json
from types import SimpleNamespace
from pathlib import Path

from collect_final_games import builder, fetch, CACHE
from rebuild_annual_totals import load_builder, read_manifest
from npb_boxscore_stats import _Tree, TEAMS, normalize_name

ROOT = Path(__file__).resolve().parent.parent


def main():
    report = json.loads((ROOT / 'docs/pitcher-official-audit.json').read_text(encoding='utf-8'))
    entries = read_manifest('manifest.js')
    module, site = builder(), load_builder()
    missing = report['unmatchedOfficialRows']
    if not missing:
        print('No missing official appearances; existing collection evidence retained.')
        return
    collected = []
    for game_id in sorted({row[0] for row in missing}):
        game_entry = next(e for e in entries if e['gameId'] == game_id)
        html = (ROOT / '.site-build/pitcher-official-audit' / f'{game_id}.html').read_text(encoding='utf-8')
        tree = _Tree(html)
        targets = []
        for gid, side, name in missing:
            if gid != game_id:
                continue
            table = next(t for t in tree.root.descendants('table') if t.attrs.get('id') == side)
            section = table.parent
            while section.tag != 'section':
                section = section.parent
            team = TEAMS[next(section.descendants('h4')).text().strip()]
            identities = {(e['pitcherId'], e['player']) for e in entries
                          if e['team'] == team and normalize_name(e['player']).startswith(name)}
            assert len(identities) == 1, (team, name, identities)
            pitcher_id, player = identities.pop()
            targets.append((team, pitcher_id, player))
        stats_html = fetch(f'https://baseball.yahoo.co.jp/npb/game/{game_id}/stats')
        pages, seen, index = [], set(), None
        pages_path = CACHE / f'{game_id}-pages.json'
        if pages_path.exists():
            pages = json.loads(pages_path.read_text(encoding='utf-8'))
        else:
            while True:
                url = f'https://baseball.yahoo.co.jp/npb/game/{game_id}/score'
                if index:
                    url += '?index=' + index
                page = module.parse_score_page_html(fetch(url), index)
                pages.append(page)
                index = page['prev']
                if not index:
                    break
                assert index not in seen, ('Navigation loop', game_id, index)
                seen.add(index)
                if len(pages) % 20 == 0:
                    print(game_id, 'play pages:', len(pages), flush=True)
            pages_path.write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
        session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(text=stats_html, raise_for_status=lambda: None))
        for team, pitcher_id, player in targets:
            pitches = module.collect_pitcher_rows(pages, None, pitcher_id)
            statline, metadata = module.parse_statline(session, game_id, None, pitcher_id)
            assert len(pitches) == int(statline['pitches']), (player, len(pitches), statline)
            assert all(p['left'] is not None and p['top'] is not None for p in pitches)
            prefix = module.sanitize_filename(f'{game_id}-{statline["player"]}')
            path = ROOT / 'generated' / team / game_entry['date'] / f'{prefix}-dashboard.json'
            assert not path.exists(), ('Refuse overwrite', path)
            payload = {'game_id': game_id, 'metadata': metadata, 'statline': statline, 'pitches': pitches}
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            collected.append({'gameId': game_id, 'date': game_entry['date'], 'team': team,
                              'pitcherId': pitcher_id, 'player': player, 'pitches': len(pitches),
                              'path': path.relative_to(ROOT).as_posix()})
            print('Collected:', collected[-1], flush=True)
        decisions = site.load_game_decisions_cache()
        decisions['games'][game_id] = site.parse_game_decisions_from_html(stats_html)
        site.save_game_decisions_cache(decisions)
    (ROOT / 'docs/missing-pitcher-collection.json').write_text(
        json.dumps({'appearances': collected}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
