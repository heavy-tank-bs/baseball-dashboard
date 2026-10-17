"""Rebuild annual totals from published manifests and cached official game stats.

Run refresh_dashboard_stats.py first. No network requests are made here.
Published older seasons are retained when their raw source files are absent.
"""
from __future__ import annotations

import importlib.util
import argparse
import json
import unicodedata
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location("build_manifest", ROOT / "summary/build_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_manifest(name):
    text = (ROOT / "summary" / name).read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):].rstrip(";\n"))["entries"]


def load_entries(module):
    entries = read_manifest("manifest.js")
    baselines = None
    for entry in entries:
        raw_path = ROOT / "generated" / entry["team"] / entry["date"] / f"{entry['prefix']}-dashboard.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        detail_path = ROOT / "summary" / entry["detailPath"]
        if detail_path.exists():
            entry["dashboard"] = json.loads(detail_path.read_text(encoding="utf-8"))["dashboard"]
        else:
            if baselines is None:
                grouped = {(e["team"], e["date"], e["prefix"]): e for e in entries}
                baselines = module.build_league_chase_baselines(grouped)
            entry["dashboard"] = module.serialize_dashboard(raw, baselines.get(entry["league"]))
            module.write_text_atomic(detail_path, json.dumps({"id": entry["id"], "dashboard": entry["dashboard"]}, ensure_ascii=False, indent=2) + "\n")
        entry["_pitchRows"] = raw.get("pitches") or []
    return entries


def load_inputs(module, entries=None):
    entries = entries if entries is not None else load_entries(module)
    batting = module.load_game_batting_cache()["games"]
    original_batters = read_manifest("batter_manifest.js")
    def normalized(name):
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name))
    identities = {}
    names = {}
    for field, source in [("pitcherId", entries), ("batterId", original_batters)]:
        for row in source:
            if row.get(field):
                identities[(row["team"], normalized(row["player"]))] = row[field]
                names[row[field]] = row["player"]
    for gid, teams in batting.items():
        for team, rows in teams.items():
            cleaned = {}
            for key, row in rows.items():
                if key != (row.get("playerId") or row["player"]):
                    continue
                row = dict(row)
                player_id = row.get("playerId") or identities.get((team, normalized(row["player"])))
                if not player_id:
                    raise ValueError(f"Unresolved batting identity: {gid} {team} {row['player']}")
                row["playerId"] = player_id
                row["player"] = names.get(player_id, row["player"])
                cleaned[player_id] = row
                cleaned[row["player"]] = row
            teams[team] = cleaned
    decisions = module.load_game_decisions_cache()["games"]
    ids = {entry["gameId"] for entry in entries}
    if not ids.issubset(batting) or not ids.issubset(decisions):
        raise ValueError("Incomplete stats cache: run scripts/refresh_dashboard_stats.py first")
    for gid in ids:
        if len(batting[gid]) != 2 or any(not rows or any("plateAppearances" not in row for row in rows.values()) for rows in batting[gid].values()):
            raise ValueError(f"Invalid batting cache for {gid}")
    cache = module.load_game_batting_cache()
    cache["games"] = batting
    module.save_game_batting_cache(cache)
    batting = {gid: batting[gid] for gid in ids}
    batters = module.collect_batter_entries(batting, module.load_uniform_number_index("batter"))
    return entries, decisions, batting, batters


def preserve_other_years(current, previous):
    years = set(current["years"])
    for key in ("players", "leagueStats"):
        if key in current:
            current[key] = [row for row in previous.get(key, []) if row["year"] not in years] + current[key]
    for key, rows in current.get("metricContexts", {}).items():
        current["metricContexts"][key] = [row for row in previous.get("metricContexts", {}).get(key, []) if row["year"] not in years] + rows
    current["years"] = sorted(years | set(previous.get("years", [])))
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-details-only", action="store_true")
    parser.add_argument("--refresh-manifests", action="store_true", help="Discover new generated games and refresh every pitcher detail")
    parser.add_argument("--pitcher-manifest-only", action="store_true", help="Discover games before refreshing official batting caches")
    args = parser.parse_args()
    m = load_builder()
    if args.repair_details_only:
        print("Verified/repaired detail assets:", len(load_entries(m)), flush=True)
        return
    entries = None
    if args.refresh_manifests or args.pitcher_manifest_only:
        entries = m.collect_entries(m.load_uniform_number_index('pitcher'))
        m.write_pitcher_manifest_details(entries)
        m.write_text_atomic(m.MANIFEST_PATH, 'window.PITCH_DASHBOARD_MANIFEST = ' + m.dumps_compact(m.build_manifest(entries, m.pitcher_manifest_entry)) + ';\n')
        print('Pitcher manifest:', len(entries), 'appearances', flush=True)
        if args.pitcher_manifest_only:
            return
    entries, decisions, batting, batters = load_inputs(m, entries)
    m.write_text_atomic(m.BATTER_MANIFEST_PATH, "window.BATTER_GAME_MANIFEST = " + m.dumps_compact(m.build_manifest(batters)) + ";\n")
    contexts = m.load_game_contexts()
    parks = m.build_park_factors(contexts)
    m.write_text_atomic(m.PARK_FACTORS_PATH, json.dumps(parks, ensure_ascii=False, indent=2) + '\n')
    outputs = [
        (m.PLAYER_TOTALS_PATH, m.build_player_totals(entries, decisions, contexts)),
        (m.BATTER_TOTALS_PATH, m.build_batter_totals(entries, batting, batters, parks, contexts)),
    ]
    for path, current in outputs:
        previous = json.loads(path.read_text(encoding="utf-8"))
        result = preserve_other_years(current, previous)
        m.write_text_atomic(path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(path.name, len(result["players"]), "players", flush=True)


if __name__ == "__main__":
    main()
