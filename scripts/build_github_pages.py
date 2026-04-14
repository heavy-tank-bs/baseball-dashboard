from __future__ import annotations

import shutil
import stat
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
TEMP_SITE_DIR = ROOT / ".site-build"
SUMMARY_DIR = ROOT / "summary"
GENERATED_DIR = ROOT / "generated"

SUMMARY_FILES = (
    "index.html",
    "batter.html",
    "annual.html",
    "annual-batter.html",
    "styles.css",
    "app.js",
    "batter.js",
    "annual.js",
    "annual-batter.js",
    "manifest.js",
    "batter_manifest.js",
    "player_totals.json",
    "batter_totals.json",
)
GENERATED_EXTENSIONS = {".json", ".png"}
ROOT_INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=./summary/index.html">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Summary Site</title>
</head>
<body>
  <p><a href="./summary/index.html">Open summary site</a></p>
</body>
</html>
"""


def _handle_remove_error(function, path, exc_info) -> None:
    target = Path(path)
    if target.exists():
        target.chmod(stat.S_IWRITE)
    function(path)


def remove_tree(path: Path, retries: int = 5, delay_seconds: float = 1.0) -> None:
    for attempt in range(1, retries + 1):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onerror=_handle_remove_error)
            return
        except OSError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)


def reset_directory(path: Path) -> None:
    remove_tree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_summary_assets(target_dir: Path) -> list[Path]:
    copied_files: list[Path] = []
    for name in SUMMARY_FILES:
        source = SUMMARY_DIR / name
        if not source.exists():
            raise FileNotFoundError(f"Missing summary asset: {source}")
        target = target_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied_files.append(target)
    return copied_files


def copy_generated_assets(target_dir: Path) -> int:
    copied_count = 0
    for source in GENERATED_DIR.rglob("*"):
        if not source.is_file():
            continue
        if source.suffix.lower() not in GENERATED_EXTENSIONS:
            continue
        target = target_dir / source.relative_to(GENERATED_DIR)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied_count += 1
    return copied_count


def write_root_files(target_dir: Path) -> None:
    (target_dir / "index.html").write_text(ROOT_INDEX_HTML, encoding="utf-8")
    (target_dir / ".nojekyll").write_text("", encoding="utf-8")


def build() -> None:
    reset_directory(TEMP_SITE_DIR)
    temp_summary_dir = TEMP_SITE_DIR / "summary"
    temp_generated_dir = TEMP_SITE_DIR / "generated"
    temp_summary_dir.mkdir(parents=True, exist_ok=True)
    temp_generated_dir.mkdir(parents=True, exist_ok=True)

    summary_files = copy_summary_assets(temp_summary_dir)
    generated_count = copy_generated_assets(temp_generated_dir)
    write_root_files(TEMP_SITE_DIR)

    remove_tree(SITE_DIR)
    TEMP_SITE_DIR.replace(SITE_DIR)

    print(f"Built GitHub Pages site at: {SITE_DIR}")
    print(f"Summary assets: {len(summary_files)} files")
    print(f"Generated assets: {generated_count} files")


if __name__ == "__main__":
    build()
