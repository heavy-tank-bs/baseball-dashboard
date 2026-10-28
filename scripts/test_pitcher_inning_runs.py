"""Exact-allocation regression tests and independent season-wide conservation."""
import itertools
import json
from pathlib import Path
import unittest
from collections import Counter, defaultdict

from build_pitcher_inning_runs import (
    ROOT, VERIFIED_SCORE_REPAIRS, appearance_key, derive_appearance_intervals,
    inning_score_runs, innings_to_outs, load_manifest, normalize_team,
    solve_unique_runs,
)


class IntegerRunSolverTests(unittest.TestCase):
    def test_exhaustive_two_by_two_against_brute_force(self):
        # Exhaustively compare all small integer solutions, including dense
        # cycles, sparse trees, infeasible capacities, and zero rows/columns.
        for mask in range(16):
            cells = [(pitcher, inning) for pitcher in range(2) for inning in range(2) if mask & (1 << (pitcher * 2 + inning))]
            candidates = {pitcher: [inning for source, inning in cells if source == pitcher] for pitcher in range(2)}
            for margins in itertools.product(range(3), repeat=4):
                pitcher_totals = dict(enumerate(margins[:2]))
                inning_totals = dict(enumerate(margins[2:]))
                solutions = []
                for values in itertools.product(range(3), repeat=len(cells)):
                    if all(sum(value for (pitcher, _), value in zip(cells, values) if pitcher == key) == total for key, total in pitcher_totals.items()) and all(sum(value for (_, inning), value in zip(cells, values) if inning == key) == total for key, total in inning_totals.items()):
                        solutions.append(dict(zip(cells, values)))
                        if len(solutions) > 1:
                            break
                allocation, status = solve_unique_runs(pitcher_totals, inning_totals, candidates)
                if not solutions:
                    self.assertIn(status, ["infeasible", "total_mismatch"], (mask, margins, status))
                    self.assertIsNone(allocation)
                elif len(solutions) > 1:
                    self.assertEqual(status, "ambiguous", (mask, margins, status))
                    self.assertIsNone(allocation)
                else:
                    self.assertEqual(status, "unique", (mask, margins, status))
                    self.assertEqual({(pitcher, inning): value for pitcher, rows in allocation.items() for inning, value in rows.items() if value}, {cell: value for cell, value in solutions[0].items() if value})

    def test_inherited_runner_stays_in_exit_inning(self):
        # Both pitchers face batters in the sixth. Official totals distinguish
        # the exited pitcher's charged runs from the reliever's charged runs.
        allocation, status = solve_unique_runs({"starter": 3, "relief": 1}, {5: 1, 6: 3}, {"starter": [1, 2, 3, 4, 5, 6], "relief": [6, 7]})
        self.assertEqual(status, "unique")
        self.assertEqual(allocation, {"starter": {5: 1, 6: 2}, "relief": {6: 1}})

    def test_official_out_bounds_cover_missing_early_log_and_no_out_exit(self):
        rows, problems = derive_appearance_intervals([
            {"gameId": "g", "team": "t", "pitcherId": "starter", "order": 400, "inningsOuts": 18, "observedInnings": [4, 5, 6]},
            {"gameId": "g", "team": "t", "pitcherId": "relief", "order": 700, "inningsOuts": 3, "observedInnings": [7]},
        ])
        self.assertFalse(problems)
        self.assertEqual(rows[0]["candidateInnings"], list(range(1, 8)))
        self.assertEqual(rows[1]["candidateInnings"], [7, 8])
        # The extra seventh-inning edge is deliberate: completing six innings
        # does not prove the starter faced no batters in the seventh.

    def test_interval_conflict_is_rejected(self):
        _rows, problems = derive_appearance_intervals([
            {"gameId": "g", "team": "t", "pitcherId": "p", "order": 100, "inningsOuts": 3, "observedInnings": [4]},
        ])
        self.assertEqual(problems[0]["reason"], "observed_inning_outside_official_out_bounds")

    def test_score_notation_and_baseball_outs(self):
        self.assertEqual(inning_score_runs({"runs": None, "raw": "3X"}), 3)
        self.assertEqual(inning_score_runs({"runs": None, "raw": "0X"}), 0)
        self.assertIsNone(inning_score_runs({"runs": None, "raw": "X"}))
        self.assertEqual(innings_to_outs("6.2"), 20)
        with self.assertRaises(ValueError):
            innings_to_outs("6.3")


class PublishedSeasonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asset = json.loads((ROOT / "summary/pitcher_inning_runs_2026.json").read_text(encoding="utf-8"))
        cls.audit = json.loads((ROOT / "docs/pitcher-inning-runs-verification.json").read_text(encoding="utf-8"))
        cls.entries = load_manifest(ROOT / "summary/manifest.js")["entries"]
        cls.contexts = {str(game["gameId"]): game for game in json.loads((ROOT / "summary/sportsnavi_game_context_2026.json").read_text(encoding="utf-8"))["games"]}

    def test_every_official_appearance_run_is_conserved(self):
        self.assertTrue(self.asset["verified"])
        self.assertEqual(self.asset["coverage"]["appearances"], 7175)
        self.assertEqual(self.asset["coverage"]["verifiedAppearances"], 7175)
        self.assertEqual(self.asset["coverage"]["solutionCounts"], {"unique": 1716})
        self.assertEqual(self.asset["coverage"]["totalRuns"], 6168)
        self.assertFalse(self.audit["problems"])
        for entry in self.entries:
            with self.subTest(appearance=appearance_key(entry)):
                row = self.asset["appearances"][appearance_key(entry)]
                self.assertTrue(row["verified"])
                self.assertEqual(row["method"], "unique_integer_constraints")
                self.assertEqual(row["runs"], int(entry["statline"]["runs"]))
                self.assertEqual(sum(item["runs"] for item in row["inningRuns"]), row["runs"])
                self.assertTrue(all(1 <= item["inning"] <= 12 and isinstance(item["runs"], int) and item["runs"] > 0 for item in row["inningRuns"]))

    def test_each_game_and_inning_matches_score_table(self):
        groups = defaultdict(Counter)
        for row in self.asset["appearances"].values():
            for item in row["inningRuns"]:
                groups[row["gameId"], row["team"]][item["inning"]] += item["runs"]
        # Include verified zero-run team games in this independent check.
        for row in self.asset["appearances"].values():
            groups[row["gameId"], row["team"]]
        self.assertEqual(len(groups), 1716)
        self.assertEqual(len({game_id for game_id, _team in groups}), 858)
        for (game_id, team), actual in groups.items():
            game = self.contexts[game_id]
            side = "away" if normalize_team(game["homeTeam"]) == team else "home"
            source = game["inningScores"][side]["innings"]
            if not source:
                source = [{"inning": index + 1, "raw": value} for index, value in enumerate(VERIFIED_SCORE_REPAIRS[game_id][side])]
            expected = {int(row["inning"]): value for row in source if (value := inning_score_runs(row)) is not None and value > 0}
            self.assertEqual(dict(actual), expected, (game_id, team))
            self.assertEqual(sum(actual.values()), int(game[f"{side}Score"]), (game_id, team))

    def test_each_player_season_matches_published_annual_runs(self):
        annual = json.loads((ROOT / "summary/player_totals.json").read_text(encoding="utf-8"))
        rows = [row for row in annual["players"] if row["year"] == "2026"]
        id_counts = Counter(row["pitcherId"] for row in rows)
        for row in rows:
            appearances = [appearance for appearance in self.asset["appearances"].values() if appearance["pitcherId"] == row["pitcherId"] and (id_counts[row["pitcherId"]] == 1 or appearance["team"] in row.get("sourceTeams", row.get("teams", [row["team"]])))]
            self.assertEqual(sum(appearance["runs"] for appearance in appearances), row["runs"], (row["pitcherId"], row["team"]))
        self.assertEqual(sum(row["runs"] for row in rows), self.asset["coverage"]["verifiedRuns"])

    def test_exception_evidence_and_partial_raw_game(self):
        self.assertEqual(len(self.audit["scoreTableRepairs"]), 6)
        self.assertEqual({row["gameId"] for row in self.audit["scoreTableRepairs"]}, set(VERIFIED_SCORE_REPAIRS))
        self.assertEqual(len(self.audit["intervalEvidence"]), 2)
        self.assertTrue(all(row["sourceUrl"].startswith("https://baseball.yahoo.co.jp/npb/game/") for row in self.audit["scoreTableRepairs"] + self.audit["intervalEvidence"]))
        kitayama = self.asset["appearances"]["2021039181::日本ハム::1750903"]
        sumida = self.asset["appearances"]["2021039181::西武::1751148"]
        self.assertEqual(kitayama["inningRuns"], [{"inning": 2, "runs": 1}])
        self.assertEqual(sumida["inningRuns"], [{"inning": 3, "runs": 3}, {"inning": 4, "runs": 4}])


if __name__ == "__main__":
    unittest.main()
