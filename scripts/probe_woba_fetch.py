"""Small, sequential diagnostics for public play-by-play sources."""
from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local", type=Path)
    args = parser.parse_args()
    if args.local:
        from bs4 import BeautifulSoup
        html = gzip.decompress(args.local.read_bytes()).decode("utf-8") if args.local.suffix == '.gz' else args.local.read_text(encoding='utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        progress = soup.select_one('#progress')
        for node in (progress or soup).find_all(['h5', 'tr']):
            print(node.get_text(' | ', strip=True))
        return
    results = []
    with requests.Session() as session:
        for url in args.urls:
            start = time.monotonic()
            try:
                response = session.get(url, timeout=30)
                response.encoding = "utf-8"
                record = {"url": url, "status": response.status_code,
                          "elapsed": round(time.monotonic() - start, 2),
                          "bytes": len(response.content),
                          "headers": dict(response.headers),
                          "snippet": response.text[:300]}
                if args.output:
                    args.output.mkdir(parents=True, exist_ok=True)
                    (args.output / f"probe-{len(results) + 1}.html").write_text(response.text, encoding="utf-8")
            except requests.RequestException as exc:
                record = {"url": url, "error": str(exc)}
            results.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            time.sleep(1)
    if args.output:
        (args.output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
