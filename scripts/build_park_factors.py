from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_DIR = ROOT / "summary"
BUILD_MANIFEST_PATH = SUMMARY_DIR / "build_manifest.py"
OUTPUT_PATH = SUMMARY_DIR / "park_factors.json"


def load_build_manifest_module():
    spec = importlib.util.spec_from_file_location("summary_build_manifest", BUILD_MANIFEST_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    build_manifest = load_build_manifest_module()
    contexts = build_manifest.load_game_contexts()
    park_factors = build_manifest.build_park_factors(contexts)
    OUTPUT_PATH.write_text(json.dumps(park_factors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"output: {OUTPUT_PATH}")
    print(f"seasons: {park_factors['seasons']}")


if __name__ == "__main__":
    main()
