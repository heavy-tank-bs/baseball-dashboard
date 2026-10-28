"""Apply verified 2026 inning summaries without rebuilding unrelated metrics.

The default is a dry run. --write changes only the two inning tables and their
verification metadata inside 2026 pitcher seasonDashboard objects.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"inningSummaryCoverage", "inningRunRowsMethod", "inningRunRowsScope", "inningRunRowsAvailable",
          "inningWalkRowsMethod", "inningWalkRowsScope", "inningWalkRowsAvailable", "inningRunRows", "inningWalkRows"}


def load_builder(extra_names=()):
    # Use the builder's actual pure functions without importing its plotting,
    # image and network stack; this targeted update requires only stdlib.
    target = ROOT / "summary/build_manifest.py"
    tree = ast.parse(target.read_text(encoding="utf-8"))
    names = {"safe_load_json", "normalize_team_name", "team_league", "parse_int", "parse_float", "configure_annual_affiliations",
             "annual_player_key", "resolve_game_decision", "pitcher_decision_key", "build_annual_stat_bucket",
             "season_dashboard_source", "verified_pitcher_inning_appearance", "record_verified_pitcher_inning_summaries",
             "finalize_pitcher_inning_summaries"}
    names.update(extra_names)
    constants = {"TEAM_LEAGUES", "TEAM_ALIASES", "VERIFIED_PITCHER_INNING_METHOD"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names or
             isinstance(node, ast.Assign) and any(isinstance(name, ast.Name) and name.id in constants for name in node.targets)]
    assert {node.name for node in nodes if isinstance(node, ast.FunctionDef)} == names
    namespace = {"json": json, "Path": Path, "Counter": Counter, "defaultdict": defaultdict,
                 "SUMMARY_DIR": ROOT / "summary", "INNING_SLOTS": list(range(1, 13)),
                 "_VERIFIED_PITCHER_INNING_CACHE": {}, "_ANNUAL_AFFILIATIONS": {}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(target), "exec"), namespace)
    return SimpleNamespace(**namespace)


def prepare_updates(payload=None):
    builder = load_builder()
    source_text = (ROOT / "summary/manifest.js").read_text(encoding="utf-8")
    entries = json.loads(source_text[source_text.index("{"):source_text.rindex("}") + 1])["entries"]
    entries = [row for row in entries if row["date"][:4] == "2026"]
    decisions = json.loads((ROOT / "summary/game_decisions_cache.json").read_text(encoding="utf-8"))["games"]
    if payload is None:
        payload = json.loads((ROOT / "summary/player_totals.json").read_text(encoding="utf-8"))
    updated = copy.deepcopy(payload)
    builder.configure_annual_affiliations(entries, "pitcherId")
    sources, expected = {}, defaultdict(Counter)
    for entry in entries:
        key = builder.annual_player_key("2026", entry["pitcherId"], entry["team"], entry["player"])
        source = sources.setdefault(key, builder.season_dashboard_source({}))
        decision_row = builder.resolve_game_decision(entry, decisions)
        builder.record_verified_pitcher_inning_summaries(source, entry, decision_row)
        decision = builder.pitcher_decision_key(decision_row)
        expected[key]["games"] += 1
        expected[key]["runs"] += int(entry["statline"]["runs"])
        expected[key]["walksAndHbp"] += int(entry["statline"]["bb"]) + int(entry["statline"]["hbp"])
        expected[key][f"runs:{decision}"] += int(entry["statline"]["runs"])
        expected[key][f"walksAndHbp:{decision}"] += int(entry["statline"]["bb"]) + int(entry["statline"]["hbp"])
    totals = Counter()
    updated_keys = set()
    for player in updated["players"]:
        if player["year"] != "2026":
            continue
        key = player.get("aggregationKey") or builder.annual_player_key("2026", player["pitcherId"], player["team"], player["player"])
        assert key in sources, f"Annual player has no exact appearance coverage: {key}"
        result = builder.finalize_pitcher_inning_summaries(sources[key])
        assert set(result) == FIELDS
        assert result["inningRunRowsAvailable"] and result["inningWalkRowsAvailable"], f"Incomplete annual summary: {key}"
        assert result["inningSummaryCoverage"]["appearancesExpected"] == player["games"] == expected[key]["games"]
        for field, metric, official in (("inningRunRows", "runs", int(player["runs"])),
                                        ("inningWalkRows", "walksAndHbp", int(player["walks"]) + int(player["hitByPitch"]))):
            assert sum(row["total"] for row in result[field]) == official == expected[key][metric], f"Annual count mismatch: {key} {field}"
            for decision in ("win", "loss", "noDecision"):
                assert sum(row[decision] for row in result[field]) == expected[key][f"{metric}:{decision}"], f"Decision count mismatch: {key} {field} {decision}"
                totals["decisionChecks"] += 1
            totals[metric] += official
        player.setdefault("seasonDashboard", {}).update(result)
        updated_keys.add(key)
    assert updated_keys == set(sources), "Unexpected appearance-only annual identities"
    for before, after in zip(payload["players"], updated["players"]):
        if before["year"] != "2026":
            assert before == after, "Other season was modified"
            continue
        old_dashboard = before.get("seasonDashboard") or {}
        new_dashboard = after.get("seasonDashboard") or {}
        assert {key: value for key, value in old_dashboard.items() if key not in FIELDS} == {key: value for key, value in new_dashboard.items() if key not in FIELDS}, "Unrelated dashboard field changed"
        assert {key: value for key, value in before.items() if key != "seasonDashboard"} == {key: value for key, value in after.items() if key != "seasonDashboard"}, "Annual metric changed"
    return updated, {"season": "2026", "playerSeasons": len(updated_keys), "appearances": len(entries), **dict(totals), "updatedFields": sorted(FIELDS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload, report = prepare_updates()
    if args.write:
        (ROOT / "summary/player_totals.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": args.write, **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
