"""Inspect saved batting-order splits and the game rows that produced them."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    totals = json.loads((ROOT / 'summary/batter_totals.json').read_text(encoding='utf-8'))
    for row in totals['players']:
        if row['player'].replace(' ', '').replace('　', '') == '佐藤輝明':
            print(json.dumps({'year': row['year'], 'batterId': row['batterId'], 'player': row['player'],
                              'byBattingOrder': row.get('seasonDashboard', {}).get('byBattingOrder')}, ensure_ascii=False))
    text = (ROOT / 'summary/batter_manifest.js').read_text(encoding='utf-8')
    entries = json.loads(text[text.index('{'):].rstrip(';\n'))['entries']
    rows = [e for e in entries if e['player'].replace(' ', '').replace('　', '') == '佐藤輝明']
    print('orders', Counter(e['order'] for e in rows))
    print(json.dumps([{k: e[k] for k in ('gameId','date','player','batterId','order','statline')}
                      for e in rows if e['order'] == 8][:3], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
