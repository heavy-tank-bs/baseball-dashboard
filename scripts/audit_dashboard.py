import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '.site-build' / 'audit'
OUT.mkdir(parents=True, exist_ok=True)

def get_month(month):
    path = OUT / f'npb-2026-{month:02}.html'
    url = f'https://npb.jp/games/2026/schedule_{month:02}_detail.html'
    if not path.exists():
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        response.encoding = 'utf-8'
        path.write_text(response.text, encoding='utf-8')
    return month, BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')

if __name__ == '__main__':
    s=(ROOT/'summary/manifest.js').read_text(encoding='utf-8')
    entries=json.loads(s[s.index('{'):].rstrip(';\n'))['entries']
    by_game={}
    for e in entries:
        by_game.setdefault(e['gameId'], {'date':e['date'],'teams':set()})['teams'].add(e['team'])
    local={(v['date'],tuple(sorted(v['teams']))):k for k,v in by_game.items()}
    official=[]
    for month, soup in ThreadPoolExecutor(max_workers=4).map(get_month, range(3, 11)):
        for tr in soup.select('tr'):
            score1,score2=tr.select_one('.score1'),tr.select_one('.score2')
            if not score1 or not score2 or not score1.text.strip().isdigit() or not score2.text.strip().isdigit(): continue
            match=re.search(r'/scores/2026/(\d{2})(\d{2})/',score1.parent.get('href',''))
            if not match: continue
            date=f'2026-{match[1]}-{match[2]}'
            if date<'2026-03-27' or date>'2026-10-08': continue
            teams=[n.text.strip().replace('楽天','東北楽天') for n in tr.select('.team1,.team2')]
            if any(t not in {'巨人','阪神','DeNA','広島','ヤクルト','中日','ソフトバンク','日本ハム','ロッテ','オリックス','西武','東北楽天'} for t in teams): continue
            key=(date,tuple(sorted(teams)))
            official.append({'date':date,'teams':teams,'url':'https://npb.jp'+score1.parent['href'],'gameId':local.get(key)})
    official.sort(key=lambda g:(g['date'],g['teams']))
    (OUT/'official-games.json').write_text(json.dumps(official,ensure_ascii=False,indent=2),encoding='utf-8')
    keys={(g['date'],tuple(sorted(g['teams']))) for g in official}
    result={'scope':'2026 regular season','officialGames':len(official),'localGames':len(by_game),'missing':[g for g in official if not g['gameId']], 'extra':[{'gameId':gid,'date':date,'teams':teams} for (date,teams),gid in local.items() if (date,teams) not in keys],'teams':[]}
    for team in sorted({t for g in official for t in g['teams']}):
        games=[g for g in official if team in g['teams']]
        result['teams'].append({'team':team,'official':len(games),'collected':sum(bool(g['gameId']) for g in games),'lastOfficial':games[-1]['date'],'lastCollected':max(g['date'] for g in games if g['gameId'])})
    report_dir = ROOT / 'docs'
    report_dir.mkdir(exist_ok=True)
    (report_dir/'coverage-2026.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
