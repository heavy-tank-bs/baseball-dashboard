"""Regression tests for durable and targeted annual inning-summary updates."""
import copy
import json
import unittest

import apply_pitcher_inning_summaries as updater


class AnnualInningSummaryIntegration(unittest.TestCase):
    def test_all_annual_and_decision_totals_and_narrow_update(self):
        original = json.loads((updater.ROOT / "summary/player_totals.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(original)
        updated, report = updater.prepare_updates(original)
        self.assertEqual(original, before, "Dry run changed its input")
        self.assertEqual(report["playerSeasons"], 385)
        self.assertEqual(report["appearances"], 7175)
        self.assertEqual(report["decisionChecks"], 2310)
        self.assertEqual(report["runs"], 6168)
        self.assertEqual(report["walksAndHbp"], 5473)
        for old, new in zip(original["players"], updated["players"]):
            if old["year"] != "2026":
                self.assertEqual(old, new)
                continue
            self.assertEqual({key: value for key, value in old.items() if key != "seasonDashboard"},
                             {key: value for key, value in new.items() if key != "seasonDashboard"})
            self.assertTrue(new["seasonDashboard"]["inningRunRowsAvailable"])
            self.assertTrue(new["seasonDashboard"]["inningWalkRowsAvailable"])
            self.assertEqual(new["seasonDashboard"]["inningWalkRowsScope"], "complete_appearances")

    def fixture(self, runs=0, walks=0, hbp=0):
        builder = updater.load_builder(["add_season_dashboard_entry"])
        namespace = builder.add_season_dashboard_entry.__globals__
        namespace.update({"build_pitcher_batter_hand_rows": lambda rows: [],
                          "matchup_opponent_team": lambda *args: "", "team_sort_key": lambda name: (0,),
                          "build_pitcher_game_split_bucket": lambda *args: {},
                          "record_pitcher_game_split": lambda *args: None,
                          "build_recent_pitcher_game_row": lambda entry: {"gameId": entry["gameId"]}})
        entry = {"date": "2099-04-01", "gameId": "g", "team": "オリックス", "pitcherId": "p",
                 "dashboard": {"pitchMix": []}, "statline": {"runs": runs, "bb": walks, "hbp": hbp}}
        key = "g::オリックス::p"
        cache = namespace["_VERIFIED_PITCHER_INNING_CACHE"]
        cache["2099", "runs"] = {key: {"verified": True, "runs": runs, "inningRuns": [{"inning": 8, "runs": runs}]}}
        cache["2099", "walks"] = {key: {"verified": True, "walks": walks, "hitByPitch": hbp,
                                               "byInning": {"8": {"walks": walks, "hitByPitch": hbp, "walksAndHbp": walks + hbp}}}}
        return builder, entry, cache, key

    def test_no_pitch_appearance_is_counted_and_all_zero_is_available(self):
        builder, entry, _cache, _key = self.fixture()
        bucket = {}
        builder.add_season_dashboard_entry(bucket, entry)
        source = bucket["_seasonDashboardSource"]
        result = builder.finalize_pitcher_inning_summaries(source)
        self.assertTrue(source["hasData"])
        self.assertEqual(result["inningSummaryCoverage"], {"appearancesExpected": 1, "runVerifiedAppearances": 1, "walkVerifiedAppearances": 1})
        self.assertTrue(result["inningRunRowsAvailable"])
        self.assertTrue(result["inningWalkRowsAvailable"])
        self.assertEqual(sum(row["total"] for row in result["inningRunRows"]), 0)

    def test_no_pitch_ibb_is_included_in_correct_decision(self):
        builder, entry, _cache, _key = self.fixture(walks=1)
        bucket = {}
        builder.add_season_dashboard_entry(bucket, entry, {"wins": 1})
        result = builder.finalize_pitcher_inning_summaries(bucket["_seasonDashboardSource"])
        eighth = next(row for row in result["inningWalkRows"] if row["inning"] == 8)
        self.assertEqual(eighth, {"inning": 8, "win": 1, "loss": 0, "noDecision": 0, "total": 1})

    def test_incomplete_coverage_is_unavailable_and_corrupt_artifact_fails(self):
        builder, entry, cache, key = self.fixture()
        cache["2099", "walks"] = {}
        source = builder.season_dashboard_source({})
        builder.record_verified_pitcher_inning_summaries(source, entry)
        result = builder.finalize_pitcher_inning_summaries(source)
        self.assertTrue(result["inningRunRowsAvailable"])
        self.assertFalse(result["inningWalkRowsAvailable"])
        cache["2099", "runs"][key]["inningRuns"][0]["runs"] = 1
        with self.assertRaises(ValueError):
            builder.verified_pitcher_inning_appearance(entry, "runs")


if __name__ == "__main__":
    unittest.main()
