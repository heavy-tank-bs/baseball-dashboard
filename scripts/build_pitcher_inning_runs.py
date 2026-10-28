"""Verify exact per-inning charged pitcher runs using conserved official totals.

For a defensive team, each pitcher's charged runs must equal its official game
stat line and each inning's charged runs must equal the opponent's inning score.
A pitcher can only be charged in an inning in which they appeared (an inherited
runner can score after exit, but only in that same inning). We publish an integer
transportation solution only if it is feasible and unique; never proportionally
allocate runs. All source files are local, and unresolved games stop publication.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEAM_NAMES = {
    "広島東洋カープ": "広島", "阪神タイガース": "阪神", "横浜DeNAベイスターズ": "DeNA",
    "読売ジャイアンツ": "巨人", "東京ヤクルトスワローズ": "ヤクルト", "中日ドラゴンズ": "中日",
    "福岡ソフトバンクホークス": "ソフトバンク", "北海道日本ハムファイターズ": "日本ハム",
    "千葉ロッテマリーンズ": "ロッテ", "オリックス・バファローズ": "オリックス",
    "埼玉西武ライオンズ": "西武", "東北楽天ゴールデンイーグルス": "東北楽天", "楽天": "東北楽天",
}
TEAMS = set(TEAM_NAMES.values())
# Re-read directly from the linked Sports Navi score tables on 2026-10-29.
# These three cached contexts had empty inning arrays; keep the repairs explicit
# and auditable rather than allocating a game total across unknown innings.
VERIFIED_SCORE_REPAIRS = {
    "2021039189": {"home": ["0", "0", "1", "0", "0", "0", "0", "0", "0", "1X"], "away": ["0", "0", "0", "0", "0", "0", "0", "0", "1", "0"]},
    "2021039192": {"home": ["1", "0", "0", "0", "0", "0", "1", "1", "1X"], "away": ["0", "1", "0", "1", "0", "0", "0", "1", "0"]},
    "2021039194": {"home": ["3", "0", "0", "0", "0", "0", "1", "1", "X"], "away": ["0", "1", "0", "0", "2", "0", "0", "0", "0"]},
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path):
    source = path.read_text(encoding="utf-8")
    return json.loads(source[source.index("{"):source.rindex("}") + 1])


def normalize_team(value):
    return TEAM_NAMES.get(value, value)


def appearance_key(entry):
    return f"{entry['gameId']}::{entry['team']}::{entry['pitcherId']}"


def parse_inning(value):
    match = re.match(r"^(\d{2})[12]", str(value or ""))
    if not match:
        return None
    inning = int(match[1])
    return inning if 1 <= inning <= 12 else None


def innings_to_outs(value):
    match = re.fullmatch(r"(\d+)(?:\.([012]))?", str(value).strip())
    if not match:
        raise ValueError(f"Invalid baseball innings: {value!r}")
    return int(match[1]) * 3 + int(match[2] or 0)


def derive_appearance_intervals(rows):
    """Bound continuous stints from official outs and chronological order.

    Required row fields: gameId/team/pitcherId/order/inningsOuts/observedInnings.
    Rows must be for one defensive team in one game. A pitcher enters in the
    inning containing the next out after all preceding pitchers' official outs.
    The exit boundary also includes the next inning if the pitcher completed an
    inning: facing batters there without recording an out (including no-pitch
    intentional walks) cannot be ruled out from the IP total alone. This is a
    conservative superset, and uniqueness is checked with those extra edges.
    """
    enriched, problems = [], []
    previous_outs = 0
    orders = [row["order"] for row in rows]
    if len(orders) != len(set(orders)):
        return [], [{"reason": "appearance_order_tie", "orders": orders}]
    for row in sorted(rows, key=lambda item: item["order"]):
        start = previous_outs // 3 + 1
        previous_outs += row["inningsOuts"]
        end = previous_outs // 3 + 1
        candidate = list(range(start, min(end, 12) + 1))
        unknown = sorted(set(row["observedInnings"]) - set(candidate))
        if unknown:
            problems.append({"appearance": appearance_key(row), "reason": "observed_inning_outside_official_out_bounds", "observed": row["observedInnings"], "candidate": candidate})
        enriched.append({**row, "candidateInnings": candidate, "intervalMethod": "official_outs_and_chronological_order"})
    return enriched, problems


def inning_score_runs(row):
    """A walk-off score such as '3X' contains three runs, whereas 'X' is unplayed."""
    if row.get("runs") is not None:
        return int(row["runs"])
    match = re.fullmatch(r"(\d+)(?:[xXｘＸ])?", str(row.get("raw") or "").strip())
    return int(match[1]) if match else None


class Flow:
    def __init__(self, size):
        self.graph = [[] for _ in range(size)]

    def edge(self, source, target, capacity):
        forward = [target, capacity, len(self.graph[target])]
        reverse = [source, 0, len(self.graph[source])]
        self.graph[source].append(forward)
        self.graph[target].append(reverse)
        return forward, reverse

    def max_flow(self, source, sink):
        total = 0
        while True:
            parent = {source: None}
            queue = deque([source])
            while queue and sink not in parent:
                node = queue.popleft()
                for index, edge in enumerate(self.graph[node]):
                    if edge[1] > 0 and edge[0] not in parent:
                        parent[edge[0]] = node, index
                        queue.append(edge[0])
            if sink not in parent:
                return total
            amount = 10**9
            node = sink
            while node != source:
                previous, index = parent[node]
                amount = min(amount, self.graph[previous][index][1])
                node = previous
            node = sink
            while node != source:
                previous, index = parent[node]
                edge = self.graph[previous][index]
                edge[1] -= amount
                self.graph[node][edge[2]][1] += amount
                node = previous
            total += amount


def solve_unique_runs(pitcher_totals, inning_totals, pitcher_innings):
    """Return a unique nonnegative integer allocation, or its failure reason.

    Uniqueness is verified with the exact residual network. Decreasing any
    positive cell is an alternative solution iff a distinct residual path can
    increase other cells from that pitcher to that inning. Excluding the same
    physical cell prevents a meaningless edge/reverse-edge two-cycle.
    """
    if any(value < 0 for value in [*pitcher_totals.values(), *inning_totals.values()]):
        return None, "negative_totals"
    if sum(pitcher_totals.values()) != sum(inning_totals.values()):
        return None, "total_mismatch"
    pitchers = list(pitcher_totals)
    innings = list(inning_totals)
    pitcher_nodes = {key: index + 1 for index, key in enumerate(pitchers)}
    inning_nodes = {inning: len(pitchers) + index + 1 for index, inning in enumerate(innings)}
    sink = len(pitchers) + len(innings) + 1
    flow = Flow(sink + 1)
    for key, total in pitcher_totals.items():
        flow.edge(0, pitcher_nodes[key], total)
    for inning, total in inning_totals.items():
        flow.edge(inning_nodes[inning], sink, total)
    cells = {}
    for key, total in pitcher_totals.items():
        for inning in pitcher_innings.get(key, []):
            if inning in inning_nodes:
                capacity = min(total, inning_totals[inning])
                forward, reverse = flow.edge(pitcher_nodes[key], inning_nodes[inning], capacity)
                cells[key, inning] = forward, reverse
    if flow.max_flow(0, sink) != sum(pitcher_totals.values()):
        return None, "infeasible"
    residual = defaultdict(list)
    allocation = {key: {} for key in pitchers}
    for (key, inning), (forward, reverse) in cells.items():
        edge_id = key, inning
        left, right = pitcher_nodes[key], inning_nodes[inning]
        if forward[1] > 0:
            residual[left].append((right, edge_id))
        if reverse[1] > 0:
            residual[right].append((left, edge_id))
            allocation[key][inning] = reverse[1]
    for (key, inning), (_forward, reverse) in cells.items():
        if reverse[1] <= 0:
            continue
        start, target = pitcher_nodes[key], inning_nodes[inning]
        forbidden = key, inning
        visited, queue = {start}, deque([start])
        while queue:
            node = queue.popleft()
            for neighbour, edge_id in residual[node]:
                if edge_id == forbidden or neighbour in visited:
                    continue
                if neighbour == target:
                    return None, "ambiguous"
                visited.add(neighbour)
                queue.append(neighbour)
    return allocation, "unique"


def read_appearances(root, entries):
    appearances = []
    problems = []
    stats = Counter()
    raw_digest = hashlib.sha256()
    for entry in entries:
        if entry.get("date", "")[:4] != "2026" or entry.get("team") not in TEAMS:
            continue
        raw_path = root / "generated" / entry["team"] / entry["date"] / f"{entry['prefix']}-dashboard.json"
        raw_bytes = raw_path.read_bytes()
        raw_digest.update(str(raw_path.relative_to(root)).replace("\\", "/").encode("utf-8") + b"\0" + raw_bytes)
        raw = json.loads(raw_bytes.decode("utf-8"))
        pitches = raw.get("pitches") or []
        innings = sorted({inning for row in pitches if (inning := parse_inning(row.get("pa_index"))) is not None})
        stats["rawPitchRows"] += len(pitches)
        stats["unknownInningPitchRows"] += sum(parse_inning(row.get("pa_index")) is None for row in pitches)
        statline = entry.get("statline") or {}
        raw_runs = (raw.get("statline") or {}).get("runs")
        runs = int(statline["runs"])
        if raw_runs is not None and int(raw_runs) != runs:
            problems.append({"appearance": appearance_key(entry), "reason": "manifest_raw_runs_mismatch", "manifest": runs, "raw": raw_runs})
        appearance = {
            "gameId": entry["gameId"], "team": entry["team"], "pitcherId": str(entry["pitcherId"]),
            "player": entry["player"], "date": entry["date"], "runs": runs,
            "observedInnings": innings,
            "candidateInnings": list(range(min(innings), max(innings) + 1)) if innings else [],
            "officialPitches": int(statline.get("pitches") or 0), "rawPitchRows": len(pitches),
            "inningsOuts": innings_to_outs(statline["innings"]),
            "order": min((int(row["pa_index"]) for row in pitches if parse_inning(row.get("pa_index")) is not None), default=int(entry.get("order") or 10**9)),
        }
        if not innings:
            problems.append({"appearance": appearance_key(entry), "reason": "no_observed_inning", "runs": runs})
        appearances.append(appearance)
    return appearances, problems, {**dict(stats), "rawInputSha256": raw_digest.hexdigest()}


def verify_season_runs(root, appearances):
    annual_path = root / "summary/player_totals.json"
    annual = [row for row in load_json(annual_path)["players"] if row["year"] == "2026"]
    id_counts = Counter(row["pitcherId"] for row in annual)
    mismatches = []
    for row in annual:
        source_teams = row.get("sourceTeams", row.get("teams", [row["team"]]))
        source_rows = [appearance for appearance in appearances.values() if appearance["pitcherId"] == row["pitcherId"] and (id_counts[row["pitcherId"]] == 1 or appearance["team"] in source_teams)]
        verified_runs = sum(appearance["runs"] for appearance in source_rows)
        if verified_runs != int(row["runs"]):
            mismatches.append({"pitcherId": row["pitcherId"], "team": row["team"], "reason": "season_runs_mismatch", "annual": int(row["runs"]), "verified": verified_runs})
    annual_total = sum(int(row["runs"]) for row in annual)
    verified_total = sum(row["runs"] for row in appearances.values())
    if annual_total != verified_total:
        mismatches.append({"reason": "full_season_runs_mismatch", "annual": annual_total, "verified": verified_total})
    return {"playerSeasons": len(annual), "matchedPlayerSeasons": len(annual) - sum(row["reason"] == "season_runs_mismatch" for row in mismatches), "annualRuns": annual_total, "verifiedRuns": verified_total, "mismatches": mismatches}


def build(root=ROOT):
    manifest_path = root / "summary/manifest.js"
    context_path = root / "summary/sportsnavi_game_context_2026.json"
    manifest = load_manifest(manifest_path)
    appearances, problems, stats = read_appearances(root, manifest["entries"])
    contexts = {str(game["gameId"]): game for game in load_json(context_path)["games"] if normalize_team(game.get("homeTeam")) in TEAMS and normalize_team(game.get("awayTeam")) in TEAMS}
    groups = defaultdict(list)
    for appearance in appearances:
        groups[appearance["gameId"], appearance["team"]].append(appearance)
    methods = Counter()
    verified = {}
    repairs = []
    interval_evidence = []
    for (game_id, team), rows in sorted(groups.items()):
        game = contexts.get(game_id)
        if not game:
            problems.append({"gameId": game_id, "team": team, "reason": "missing_game_context"})
            continue
        opponent_side = "away" if normalize_team(game["homeTeam"]) == team else "home"
        inning_scores = (game.get("inningScores") or {}).get(opponent_side) or {}
        if not inning_scores.get("innings") and game_id in VERIFIED_SCORE_REPAIRS:
            raw_scores = VERIFIED_SCORE_REPAIRS[game_id][opponent_side]
            inning_scores = {"innings": [{"inning": index + 1, "runs": int(raw) if raw.isdigit() else None, "raw": raw} for index, raw in enumerate(raw_scores)]}
            repairs.append({"gameId": game_id, "battingSide": opponent_side, "rawScores": raw_scores, "sourceUrl": f"https://baseball.yahoo.co.jp/npb/game/{game_id}/stats", "verifiedOn": "2026-10-29", "reason": "cached_context_inning_array_empty"})
        totals = {int(row["inning"]): runs for row in inning_scores.get("innings", []) if (runs := inning_score_runs(row)) is not None}
        official_score = int(game[f"{opponent_side}Score"])
        if sum(totals.values()) != official_score:
            problems.append({"gameId": game_id, "team": team, "reason": "inning_score_total_mismatch", "score": official_score, "inningScoreTotal": sum(totals.values())})
            continue
        rows, interval_problems = derive_appearance_intervals(rows)
        problems.extend(interval_problems)
        if interval_problems:
            continue
        for row in rows:
            if row["observedInnings"] and row["observedInnings"][0] > row["candidateInnings"][0]:
                interval_evidence.append({"appearance": appearance_key(row), "observedInnings": row["observedInnings"], "candidateInnings": row["candidateInnings"], "inningsOuts": row["inningsOuts"], "reason": "official_outs_cover_earlier_innings_missing_from_raw_log", "sourceUrl": f"https://baseball.yahoo.co.jp/npb/game/{game_id}/stats"})
        p_totals = {appearance_key(row): row["runs"] for row in rows}
        p_innings = {appearance_key(row): row["candidateInnings"] for row in rows}
        allocation, status = solve_unique_runs(p_totals, totals, p_innings)
        methods[status] += 1
        if status != "unique":
            problems.append({"gameId": game_id, "team": team, "reason": status, "pitchers": rows, "inningScores": totals})
            continue
        for row in rows:
            key = appearance_key(row)
            inning_runs = [{"inning": inning, "runs": runs} for inning, runs in sorted(allocation[key].items())]
            assert sum(item["runs"] for item in inning_runs) == row["runs"]
            verified[key] = {key: row[key] for key in ["gameId", "team", "pitcherId", "player", "date", "runs"]}
            verified[key].update({"verified": True, "method": "unique_integer_constraints", "inningRuns": inning_runs})
    season_check = verify_season_runs(root, verified)
    problems.extend(season_check["mismatches"])
    coverage = {
        "games": len({row["gameId"] for row in appearances}), "defensiveTeams": len(groups),
        "appearances": len(appearances), "verifiedAppearances": len(verified),
        "totalRuns": sum(row["runs"] for row in appearances), "verifiedRuns": sum(row["runs"] for row in verified.values()),
        **stats, "solutionCounts": dict(methods), "unresolved": len(problems),
        "verifiedPlayerSeasons": season_check["matchedPlayerSeasons"],
    }
    audit = {
        "verifiedAt": datetime.now(timezone.utc).isoformat(), "season": 2026,
        "method": "unique_integer_constraints", "coverage": coverage, "problems": problems,
        "scoreTableRepairs": repairs,
        "intervalEvidence": interval_evidence,
        "seasonTotals": season_check,
        "proof": {
            "constraints": ["Per-pitcher runs equal the official appearance statline", "Per-inning runs across all pitchers equal the opponent's score table", "Continuous appearance intervals are bounded conservatively using chronological pitcher order and cumulative official outs"],
            "uniqueness": "Every feasible allocation was tested for an alternative integer residual-cycle flow; no alternate allocation exists.",
            "inheritedRuns": "Charged runs may score after the pitcher exits but remain within that same inning; no inning or pitcher receives a proportional allocation.",
        },
        "inputs": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [manifest_path, context_path]},
    }
    output = {"season": 2026, "method": "unique_integer_constraints", "verified": not problems, "coverage": coverage, "appearances": verified}
    return output, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write a verified asset only when every appearance resolves")
    args = parser.parse_args()
    output, audit = build()
    print(json.dumps(audit["coverage"], ensure_ascii=False, indent=2))
    if args.write:
        (ROOT / "docs/pitcher-inning-runs-verification.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if audit["problems"]:
            raise SystemExit("Unresolved data remains; no public runs asset was written. See verification report.")
        (ROOT / "summary/pitcher_inning_runs_2026.json").write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    elif audit["problems"]:
        print(json.dumps(audit["problems"][:12], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
