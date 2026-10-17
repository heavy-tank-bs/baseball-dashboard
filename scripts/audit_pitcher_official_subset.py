"""Authenticate pitcher appearances against public NPB box scores.

Defaults to pitch-count mismatches; --all covers the whole season. --apply
repairs only saved statlines after complete identity resolution, never pitch
observations. HTML is cached locally and correction evidence is preserved.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from pathlib import Path
import re
import sys
import requests

from npb_boxscore_stats import _Tree, _cells, normalize_name, TEAMS

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.site-build/pitcher-official-audit'


def fetch(url, name):
    path = CACHE / name
    if not path.exists():
        print('Fetching', url, flush=True)
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        path.write_text(response.content.decode('utf-8'), encoding='utf-8')
    return path.read_text(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Authenticate every saved pitcher appearance')
    parser.add_argument('--apply', action='store_true', help='Repair saved statlines only after every identity resolves')
    parser.add_argument('--include-collected', action='store_true', help='Include new raw appearances from missing-pitcher-collection.json before rebuilding manifests')
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    source = (ROOT / 'summary/manifest.js').read_text(encoding='utf-8')
    entries = json.loads(source[source.index('{'):].rstrip(';\n'))['entries']
    if args.include_collected:
        collection = json.loads((ROOT / 'docs/missing-pitcher-collection.json').read_text(encoding='utf-8'))
        existing = {(e['gameId'], e['team'], e['pitcherId']) for e in entries}
        for collected in collection['appearances']:
            if (collected['gameId'], collected['team'], collected['pitcherId']) in existing:
                continue
            path = (ROOT / collected['path']).resolve()
            assert path.is_relative_to(ROOT / 'generated')
            payload = json.loads(path.read_text(encoding='utf-8'))
            prefix = path.name.removesuffix('-dashboard.json')
            entries.append({**collected, 'prefix': prefix, 'statline': payload['statline'],
                            'id': f'{collected["team"]}-{collected["date"]}-{prefix}'})
    audit = json.loads((ROOT / 'docs/pitcher-aggregate-audit.json').read_text(encoding='utf-8'))
    ids = {row['entry'] for row in audit['sourceIncompleteAppearances'] if row['recordedPitches'] != row['officialPitches']}
    targets = entries if args.all else [e for e in entries if e['id'] in ids]
    teams_by_game = defaultdict(set)
    for entry in entries:
        teams_by_game[entry['gameId']].add(entry['team'])
    lookup = {(e['date'], tuple(sorted(teams_by_game[e['gameId']]))): e['gameId'] for e in targets}
    urls = {}
    for month in sorted({e['date'][5:7] for e in targets}):
        url = f'https://npb.jp/games/2026/schedule_{month}_detail.html'
        tree = _Tree(fetch(url, f'month-{month}.html'))
        for tr in tree.root.descendants('tr'):
            by_class = {c: n for n in tr.descendants('td') for c in n.attrs.get('class', '').split()}
            # Score classes can belong to spans/anchors rather than TDs.
            for tag in ('span', 'a', 'div'):
                by_class.update({c: n for n in tr.descendants(tag) for c in n.attrs.get('class', '').split()})
            if not all(k in by_class for k in ('score1', 'score2', 'team1', 'team2')):
                continue
            score = by_class['score1']
            node = score
            while node and not node.attrs.get('href'):
                node = node.parent
            href = node.attrs.get('href', '') if node else ''
            match = re.search(r'/scores/2026/(\d{2})(\d{2})/', href)
            if not match:
                continue
            key = (f'2026-{match[1]}-{match[2]}', tuple(sorted(by_class[k].text().strip().replace('楽天', '東北楽天') for k in ('team1', 'team2'))))
            if key in lookup:
                urls[lookup[key]] = 'https://npb.jp' + href + 'box.html'
    assert {e['gameId'] for e in targets} <= urls.keys(), 'Missing official schedule mapping'
    def fetch_game(item):
        gid, url = item
        return gid, _Tree(fetch(url, gid + '.html'))
    trees = dict(ThreadPoolExecutor(max_workers=4).map(fetch_game, urls.items()))
    results = []
    unresolved = []
    matched_rows = set()
    official_rows = set()
    for gid, tree in trees.items():
        for table in tree.root.descendants('table'):
            if table.attrs.get('id') in ('tablefix_t_p', 'tablefix_b_p'):
                for row in table.descendants('tr'):
                    cells = _cells(row)
                    if len(cells) == 14 and any('/bis/players/' in a.attrs.get('href', '') for a in cells[1].descendants('a')):
                        official_rows.add((gid, table.attrs['id'], normalize_name(cells[1].text())))
    for entry in targets:
        url = urls[entry['gameId']]
        tree = trees[entry['gameId']]
        candidates = []
        for table in tree.root.descendants('table'):
            if table.attrs.get('id') not in ('tablefix_t_p', 'tablefix_b_p'):
                continue
            section = table.parent
            while section and section.tag != 'section':
                section = section.parent
            heading = next(section.descendants('h4'), None) if section else None
            if TEAMS.get(heading.text().strip() if heading else '') != entry['team']:
                continue
            headers = [n.text().strip() for n in table.descendants('th')]
            for row in table.descendants('tr'):
                cells = _cells(row)
                if len(cells) != 14:
                    continue
                name = normalize_name(cells[1].text()).replace('・', '').replace('ジュニア', 'Jr.')
                full = normalize_name(entry['player']).replace('・', '').replace('ジュニア', 'Jr.')
                if name and (name in full or full in name):
                    candidates.append((cells, headers, table.attrs['id']))
        if len(candidates) > 1:
            # A surname prefix such as 森 must not override the more specific 森浦.
            longest = max(len(normalize_name(cells[1].text())) for cells, _, _ in candidates)
            candidates = [candidate for candidate in candidates
                          if len(normalize_name(candidate[0][1].text())) == longest]
        if len(candidates) != 1:
            unresolved.append({'entry': entry['id'], 'candidates': [cells[1].text() for cells, _, _ in candidates], 'source': url})
            continue
        cells, headers, table_id = candidates[0]
        official_key = (entry['gameId'], table_id, normalize_name(cells[1].text()))
        assert official_key not in matched_rows, ('Duplicate official identity', official_key)
        matched_rows.add(official_key)
        official = {field: int(cells[index].text().strip()) for field, index in
                    [('batters', 3), ('pitches', 2), ('hits', 5), ('hr', 6), ('bb', 7), ('hbp', 8), ('k', 9), ('balk', 11), ('runs', 12), ('er', 13)]}
        innings_text = normalize_name(cells[4].text()).rstrip('+')
        match = re.fullmatch(r'(\d+)(?:\.([012]))?', innings_text)
        if not match:
            match = re.fullmatch(r'(\d+?)(?:([12])/3)?', innings_text)
        assert match, (entry['id'], innings_text)
        official['inningsOuts'] = int(match[1]) * 3 + int(match[2] or 0)
        saved = {key: int(entry['statline'][key] or 0) for key in official if key != 'inningsOuts'}
        whole, _, partial = str(entry['statline']['innings']).partition('.')
        saved['inningsOuts'] = int(whole) * 3 + int(partial or 0)
        differences = {key: {'saved': saved[key], 'official': value} for key, value in official.items() if saved[key] != value}
        results.append({'entry': entry['id'], 'source': url, 'officialName': cells[1].text().strip(),
                        'headers': headers, 'official': official, 'saved': saved, 'differences': differences})
        if differences:
            print(entry['id'], differences, flush=True)
    report = {'scope': 'All saved pitcher appearances' if args.all else 'Pitch-count mismatch appearances', 'appearances': len(results),
              'officialGames': len(urls), 'matches': sum(not r['differences'] for r in results),
              'officialPitcherRows': len(official_rows), 'unmatchedOfficialRows': sorted(official_rows - matched_rows),
              'unresolved': unresolved, 'results': results}
    report_path = ROOT / ('docs/pitcher-official-audit.json' if args.all else 'docs/pitcher-official-subset-audit.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Official games:', len(urls), 'resolved:', len(results), 'unresolved:', len(unresolved),
          'statline differences:', len(results) - report['matches'], flush=True)
    if unresolved:
        print(json.dumps(unresolved, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if args.all and official_rows != matched_rows:
        raise ValueError(f'Uncollected official pitching appearances: {sorted(official_rows - matched_rows)}')
    if args.apply:
        by_id = {e['id']: e for e in entries}
        changed = []
        for result in results:
            if not result['differences']:
                continue
            entry = by_id[result['entry']]
            path = ROOT / 'generated' / entry['team'] / entry['date'] / f'{entry["prefix"]}-dashboard.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            original_pitches = json.dumps(payload['pitches'], ensure_ascii=False, sort_keys=True)
            for field, difference in result['differences'].items():
                value = difference['official']
                if field == 'inningsOuts':
                    whole, remainder = divmod(value, 3)
                    field, value = 'innings', str(whole) if not remainder else f'{whole}.{remainder}'
                payload['statline'][field] = str(value)
            assert original_pitches == json.dumps(payload['pitches'], ensure_ascii=False, sort_keys=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            changed.append(result)
        correction_path = ROOT / 'docs/pitcher-official-corrections.json'
        if changed:
            correction_path.write_text(json.dumps({'rawPitchesUnchanged': True, 'corrections': changed}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Repaired saved statlines:', len(changed), flush=True)
    elif report['matches'] != len(results):
        raise SystemExit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
