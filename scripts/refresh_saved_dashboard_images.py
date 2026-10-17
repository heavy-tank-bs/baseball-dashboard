"""Redraw existing four-page dashboard PNG sets from their matching raw JSON.

Never create new image sets or modify raw pitch data. Historical image names
without a corresponding raw JSON file are reported and left untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image

import build_dashboard

ROOT = Path(__file__).resolve().parents[1]


def refresh(report_path: Path):
    temporary = ROOT / '.site-build' / 'png-summaries'
    temporary.mkdir(parents=True, exist_ok=True)
    refreshed, skipped = [], []
    tracked = {ROOT / name for name in subprocess.check_output(
        ['git', 'ls-files', '-z', '--', 'generated'], cwd=ROOT).decode('utf-8').split('\0') if name}
    first_pages = sorted(path for path in tracked if path.name.endswith('-dashboard-1.png'))
    for first in first_pages:
        prefix = first.name.removesuffix('-dashboard-1.png')
        source = first.with_name(prefix + '-dashboard.json')
        pages = [first.with_name(f'{prefix}-dashboard-{number}.png') for number in range(1, 5)]
        if not source.exists() or source not in tracked or not all(page.exists() and page in tracked for page in pages):
            skipped.append({'firstPage': first.relative_to(ROOT).as_posix(),
                            'reason': 'No matching tracked source JSON' if not source.exists() or source not in tracked
                                      else 'Incomplete tracked image set'})
            continue
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        summary = temporary / f'{len(refreshed):03d}-{prefix}-summary.txt'
        build_dashboard.render_dashboard(payload, *pages, summary)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, f'Raw source changed: {source}'
        sizes = []
        for page in pages:
            with Image.open(page) as image:
                image.verify()
            with Image.open(page) as image:
                sizes.append(list(image.size))
        refreshed.append({'source': source.relative_to(ROOT).as_posix(), 'sourceSha256': digest,
                          'pages': [page.relative_to(ROOT).as_posix() for page in pages],
                          'dimensions': sizes})
        print(f'Rendered {len(refreshed)}: {source.relative_to(ROOT).as_posix()}', flush=True)
    report = {'refreshedSets': len(refreshed), 'refreshedImages': len(refreshed)*4,
              'rawSourcesUnchanged': True, 'refreshed': refreshed, 'skipped': skipped}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'refreshed'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'docs/dashboard-image-refresh.json')
    refresh(parser.parse_args().report)
