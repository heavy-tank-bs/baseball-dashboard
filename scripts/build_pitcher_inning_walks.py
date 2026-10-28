"""Verify every 2026 pitcher's per-inning BB/HBP against official PA events.

Raw pitch logs are read for all manifest appearances. They locate pitching
intervals and independently count terminal walks/HBP. No-pitch intentional
walks and walks charged to the preceding pitcher cannot be recovered by simply
counting each last pitcher's terminal result. Official PA inning totals and
official per-appearance counts resolve those cases only when their nonnegative
integer allocation is provably unique. Ambiguous/infeasible data abort output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from build_pitcher_inning_runs import (ROOT, TEAMS, appearance_key, load_json,
                                      load_manifest, normalize_team, parse_inning,
                                      solve_unique_runs)


METRICS = {"walks": {"uBB", "IBB"}, "hitByPitch": {"HBP"}}


def innings_to_outs(value):
    parts = str(value).split(".")
    return 3 * int(parts[0] or 0) + (int(parts[1]) if len(parts) > 1 else 0)


def read_appearances(root, entries):
    appearances, problems = [], []
    stats = Counter()
    for entry in entries:
        if entry.get("date", "")[:4] != "2026" or entry.get("team") not in TEAMS:
            continue
        raw_path = root / "generated" / entry["team"] / entry["date"] / f"{entry['prefix']}-dashboard.json"
        raw = load_json(raw_path)
        pitches = raw.get("pitches") or []
        observed = sorted({inning for pitch in pitches if (inning := parse_inning(pitch.get("pa_index"))) is not None})
        stats["rawPitchRows"] += len(pitches)
        stats["unknownInningPitchRows"] += sum(parse_inning(pitch.get("pa_index")) is None for pitch in pitches)
        statline = entry["statline"]
        finals = {}
        for pitch in pitches:
            pa_id = str(pitch.get("pa_index") or "")
            previous = finals.get(pa_id)
            if previous is None or int(pitch.get("seq") or 0) >= int(previous.get("seq") or 0):
                finals[pa_id] = pitch
        raw_by_inning = defaultdict(Counter)
        for pa_id, pitch in finals.items():
            result = (pitch.get("result") or "").split("[", 1)[0].strip()
            metric = "walks" if "四球" in result or any(term in result for term in ("申告敬遠", "敬遠", "故意四")) else "hitByPitch" if "死球" in result else None
            if metric is None:
                continue
            inning = parse_inning(pa_id)
            if inning is None:
                problems.append({"appearance": appearance_key(entry), "reason": "terminal_walk_without_inning", "paId": pa_id, "result": result})
                continue
            raw_by_inning[inning][metric] += 1
            stats[f"rawTerminal{metric[0].upper() + metric[1:]}"] += 1
        appearance = {
            "gameId": entry["gameId"], "team": entry["team"], "pitcherId": str(entry["pitcherId"]),
            "player": entry["player"], "date": entry["date"], "walks": int(statline["bb"]),
            "hitByPitch": int(statline["hbp"]), "observedInnings": observed,
            "candidateInnings": list(range(min(observed), max(observed) + 1)) if observed else [],
            "inningsOuts": innings_to_outs(statline["innings"]), "order": entry.get("order"),
            "officialPitches": int(statline.get("pitches") or 0), "rawPitchRows": len(pitches),
            "rawByInning": {inning: dict(counts) for inning, counts in sorted(raw_by_inning.items())},
        }
        for metric, source_field in (("walks", "bb"), ("hitByPitch", "hbp")):
            if int((raw.get("statline") or {})[source_field]) != appearance[metric]:
                problems.append({"appearance": appearance_key(entry), "reason": "manifest_raw_statline_mismatch", "metric": metric})
        appearances.append(appearance)
    return appearances, problems, dict(stats)


def official_inning_totals(events, contexts):
    totals = defaultdict(lambda: {metric: Counter() for metric in METRICS})
    event_counts = Counter()
    for event in events:
        if event["eventType"] not in {"uBB", "IBB", "HBP"}:
            continue
        game = contexts[str(event["gameId"])]
        batting_team = normalize_team(event["battingTeam"])
        home, away = normalize_team(game["homeTeam"]), normalize_team(game["awayTeam"])
        assert batting_team in (home, away), "Unknown official batting team"
        defensive_team = away if batting_team == home else home
        metric = "hitByPitch" if event["eventType"] == "HBP" else "walks"
        totals[str(event["gameId"]), defensive_team][metric][int(event["inning"])] += 1
        event_counts[event["eventType"]] += 1
    return totals, dict(event_counts)


def build(root=ROOT):
    manifest_path = root / "summary/manifest.js"
    context_path = root / "summary/sportsnavi_game_context_2026.json"
    event_path = root / "summary/sportsnavi_woba_events_2026.json"
    manifest = load_manifest(manifest_path)
    appearances, problems, stats = read_appearances(root, manifest["entries"])
    contexts = {str(game["gameId"]): game for game in load_json(context_path)["games"]}
    event_payload = load_json(event_path)
    assert event_payload["source"] == "NPB official play-by-play"
    events = event_payload["events"]
    assert {event["gameId"] for event in events} == {row["gameId"] for row in appearances}, "Official PA game coverage differs"
    inning_totals, event_counts = official_inning_totals(events, contexts)
    groups = defaultdict(list)
    for row in appearances:
        groups[row["gameId"], row["team"]].append(row)
    from build_pitcher_inning_runs import derive_appearance_intervals
    solutions, verified, differences = Counter(), {}, []
    for (game_id, team), rows in sorted(groups.items()):
        rows, interval_problems = derive_appearance_intervals(rows)
        problems.extend(interval_problems)
        if interval_problems:
            continue
        allocations = {}
        candidates = {appearance_key(row): row["candidateInnings"] for row in rows}
        for metric in METRICS:
            pitcher_totals = {appearance_key(row): row[metric] for row in rows}
            totals = {inning: inning_totals[game_id, team][metric][inning] for inning in range(1, 13)}
            allocation, status = solve_unique_runs(pitcher_totals, totals, candidates)
            solutions[f"{metric}:{status}"] += 1
            if status != "unique":
                problems.append({"gameId": game_id, "team": team, "metric": metric, "reason": status,
                                 "pitchers": rows, "inningTotals": totals})
                break
            allocations[metric] = allocation
        if len(allocations) != len(METRICS):
            continue
        for row in rows:
            key = appearance_key(row)
            by_inning = {
                str(inning): {"walks": allocations["walks"][key].get(inning, 0),
                              "hitByPitch": allocations["hitByPitch"][key].get(inning, 0),
                              "walksAndHbp": allocations["walks"][key].get(inning, 0) + allocations["hitByPitch"][key].get(inning, 0)}
                for inning in range(1, 13)
            }
            verified[key] = {field: row[field] for field in ("gameId", "team", "pitcherId", "player", "date", "walks", "hitByPitch")}
            verified[key].update({"verified": True, "method": "unique_official_inning_and_appearance_totals", "byInning": by_inning})
            raw_totals = {metric: sum(counts.get(metric, 0) for counts in row["rawByInning"].values()) for metric in METRICS}
            if any(raw_totals[metric] != row[metric] for metric in METRICS) or any(
                by_inning[str(inning)][metric] != row["rawByInning"].get(inning, {}).get(metric, 0)
                for inning in range(1, 13) for metric in METRICS
            ):
                differences.append({"appearance": key, "player": row["player"], "rawTerminalTotals": raw_totals,
                                    "officialTotals": {metric: row[metric] for metric in METRICS},
                                    "rawByInning": row["rawByInning"], "verifiedByInning": {inning: counts for inning, counts in by_inning.items() if counts["walksAndHbp"]},
                                    "observedInnings": row["observedInnings"], "candidateInnings": row["candidateInnings"]})
    coverage = {"games": len({row["gameId"] for row in appearances}), "defensiveTeams": len(groups),
                "appearances": len(appearances), "verifiedAppearances": len(verified),
                "walks": sum(row["walks"] for row in appearances), "hitByPitch": sum(row["hitByPitch"] for row in appearances),
                "officialEventCounts": event_counts, **stats, "solutionCounts": dict(solutions), "rawLogDifferences": len(differences), "unresolved": len(problems)}
    hashes = {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in (manifest_path, context_path, event_path)}
    audit = {"verifiedAt": datetime.now(timezone.utc).isoformat(), "season": 2026,
             "method": "Read every raw pitching log; reconcile official per-inning BB including IBB and HBP with each official appearance total using a uniquely solvable integer allocation.",
             "coverage": coverage, "inputSha256": hashes, "rawLogDifferences": differences, "problems": problems}
    payload = {"version": 1, "season": "2026", "verifiedAt": audit["verifiedAt"], "coverage": coverage,
               "source": "NPB official plate appearances, official game pitching lines, and all collected pitching logs",
               "method": "unique_official_inning_and_appearance_totals", "appearances": verified}
    return payload, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    payload, audit = build(args.root)
    report = args.report or args.root / "docs/pitcher-inning-walks-verification.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit["coverage"], ensure_ascii=False))
    if audit["problems"]:
        raise SystemExit("Unresolved exact BB/HBP innings; published output was not replaced")
    assert payload["coverage"]["appearances"] == payload["coverage"]["verifiedAppearances"]
    output = args.output or args.root / "summary/pitcher_inning_walks_2026.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
