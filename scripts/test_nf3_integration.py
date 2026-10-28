"""Regression tests for nf3 month grouping and preservation during 2026 rebuilds.

Uses temporary files and small fixtures; it never modifies published site data.
"""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import apply_nf3_2025 as integration
from apply_nf3_2025 import monthly_rows
from rebuild_annual_totals import preserve_other_years


def load_manifest_preserver():
    # Importing the complete builder also imports the PNG renderer/matplotlib.
    # Execute the actual preservation function without unrelated render tooling.
    path = Path(__file__).resolve().parents[1] / "summary/build_manifest.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definition = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "preserve_unavailable_seasons")
    namespace = {"Path": Path, "json": json}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["preserve_unavailable_seasons"]


PRESERVE_UNAVAILABLE_SEASONS = load_manifest_preserver()


def previous_seasons():
    return {
        "years": ["2025", "2026"],
        "players": [
            {"year": "2025", "player": "宮城 大弥", "sourceProvider": "nf3", "pitches": 2403,
             "monthlySplits": [{"month": "2025-03/04", "monthLabel": "3・4月", "inningsOuts": 114}]},
            {"year": "2026", "player": "Old 2026", "games": 1},
        ],
        "leagueStats": [{"year": "2025", "fipConstant": 2.7384}, {"year": "2026", "games": 1}],
        "metricContexts": {
            "wobaConstants": [{"year": "2025", "available": False}, {"year": "2026", "available": False}],
            "leagues": [{"year": "2025", "available": False, "woba": None}, {"year": "2026", "woba": 0.1}],
        },
        "sourceByYear": {
            "2025": {"name": "プロ野球 ヌルデータ置き場f3", "url": "https://nf3.sakura.ne.jp/2025/",
                     "dataset": "nf3_2025_pitchers.json", "scope": "3・4月は取得元の合算区分。"},
            "2026": {"name": "stale 2026 provenance"},
        },
    }


def rebuilt_2026():
    return {
        "years": ["2026"],
        "players": [{"year": "2026", "player": "Fresh 2026", "games": 23}],
        "leagueStats": [{"year": "2026", "games": 23}],
        "metricContexts": {
            "wobaConstants": [{"year": "2026", "available": True}],
            "leagues": [{"year": "2026", "woba": 0.301}],
        },
        "sourceByYear": {"2026": {"name": "fresh 2026 provenance"}},
    }


def source_fixture(kind):
    annual = {"games": 1, "inningsOuts": 3, "earnedRuns": 0, "homeRuns": 0,
              "walks": 1, "unintentionalWalks": 1, "intentionalWalks": 0,
              "hitByPitch": 0, "strikeouts": 1, "plateAppearances": 4, "runs": 1}
    return {
        "season": "2025", "source": {"name": "nf3 fixture", "retrievedAt": "2026-10-28T00:00:00+00:00"},
        "coverage": {"discoveredPlayers": 12, "collectedPlayers": 12, "parseFailures": [], "issues": []},
        "players": [{"team": f"Team {i}", "league": "セ" if i < 6 else "パ", "player": f"Player {i}",
                     "uniformNumber": str(i), "nf3Id": f"fixture:{i}", "sourceUrl": f"https://example.invalid/{i}",
                     "annual": copy.deepcopy(annual)} for i in range(12)],
    }


class Nf3IntegrationTests(unittest.TestCase):
    def preservation_results(self, current, previous):
        yield "rebuild_annual_totals", preserve_other_years(copy.deepcopy(current), copy.deepcopy(previous))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "published_totals.json"
            path.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
            yield "build_manifest", PRESERVE_UNAVAILABLE_SEASONS(copy.deepcopy(current), path)

    def test_combined_march_april_is_one_explicit_period(self):
        source = {"monthlySplits": [
            {"month": "3・4月", "innings": "38.0", "inningsOuts": 114, "games": 5,
             "hits": 26, "strikeouts": 37, "walks": 4, "hitByPitch": 1, "earnedRuns": 6},
            {"month": "5月", "innings": "27.0", "inningsOuts": 81, "games": 4, "strikeouts": 29},
        ]}
        original = copy.deepcopy(source)
        identity = {"player": "宮城 大弥", "team": "オリックス", "league": "パ"}
        result = monthly_rows(source, identity)
        self.assertEqual([row["month"] for row in result], ["2025-03/04", "2025-05"])
        self.assertEqual(result[0]["monthLabel"], "3・4月")
        self.assertEqual(result[0]["sourceGrouping"], "3・4月")
        self.assertEqual(sum(row["inningsOuts"] for row in result), 195)
        self.assertEqual(result[0]["strikeouts"], 37)
        self.assertEqual(result[0]["walks"], 4)
        self.assertEqual(result[0]["earnedRuns"], 6)
        self.assertIsNone(result[0]["pitches"])
        self.assertFalse(result[0]["hasPitchCount"])
        self.assertIsNone(result[0]["fip"])
        self.assertIsNone(result[0]["fipConstant"])
        for unsupported in ("intentionalWalks", "unintentionalWalks", "batters", "atBats", "whiffRate"):
            self.assertNotIn(unsupported, result[0])
        self.assertEqual(source, original)
        result[0]["walks"] = 100
        self.assertEqual(source, original)

    def test_batter_month_counts_remain_source_values(self):
        source = {"monthlySplits": [
            {"month": "2025-03/04", "sourceGrouping": "3・4月", "plateAppearances": 84,
             "atBats": 74, "hits": 22, "walks": 7, "hitByPitch": 1, "sacrificeBunts": 1,
             "sacrificeFlies": 1, "runs": 9, "runsBattedIn": 11, "strikeouts": 14},
        ]}
        result = monthly_rows(source, {"player": "Test batter", "team": "阪神", "league": "セ"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["month"], "2025-03/04")
        for field, value in source["monthlySplits"][0].items():
            self.assertEqual(result[0][field], value)
        self.assertIsNone(result[0]["wrc"])
        self.assertIsNone(result[0]["wrcPlus"])
        for unsupported in ("intentionalWalks", "unintentionalWalks", "ballZoneSwingCount", "ballZonePitchCount"):
            self.assertNotIn(unsupported, result[0])

    def test_both_rebuilders_preserve_nf3_rows_and_contexts(self):
        previous, current = previous_seasons(), rebuilt_2026()
        for name, result in self.preservation_results(current, previous):
            with self.subTest(builder=name):
                self.assertEqual(result["years"], ["2025", "2026"])
                self.assertEqual(result["players"], [previous["players"][0], current["players"][0]])
                self.assertEqual(result["leagueStats"], [previous["leagueStats"][0], current["leagueStats"][0]])
                for context in ("wobaConstants", "leagues"):
                    self.assertEqual(result["metricContexts"][context], [previous["metricContexts"][context][0], current["metricContexts"][context][0]])
                self.assertEqual(result["sourceByYear"]["2025"], previous["sourceByYear"]["2025"])
                self.assertEqual(result["sourceByYear"]["2026"], current["sourceByYear"]["2026"])

    def test_rebuilt_year_does_not_inherit_old_source(self):
        previous, current = previous_seasons(), rebuilt_2026()
        current.pop("sourceByYear")
        for name, result in self.preservation_results(current, previous):
            with self.subTest(builder=name):
                self.assertEqual(result["sourceByYear"], {"2025": previous["sourceByYear"]["2025"]})

    def test_historical_context_key_missing_from_new_builder_is_preserved(self):
        previous, current = previous_seasons(), rebuilt_2026()
        current["metricContexts"].pop("leagues")
        for name, result in self.preservation_results(current, previous):
            with self.subTest(builder=name):
                self.assertEqual(result["metricContexts"].get("leagues"), [previous["metricContexts"]["leagues"][0]])

    def test_historical_contexts_survive_absent_current_context_object(self):
        previous, current = previous_seasons(), rebuilt_2026()
        current.pop("metricContexts")
        for name, result in self.preservation_results(current, previous):
            with self.subTest(builder=name):
                expected = {key: [rows[0]] for key, rows in previous["metricContexts"].items()}
                self.assertEqual(result.get("metricContexts"), expected)

    def test_apply_preserves_2026_players_contexts_and_existing_ids(self):
        for kind, filename, id_field in (("pitchers", "player_totals.json", "pitcherId"), ("batters", "batter_totals.json", "batterId")):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "summary").mkdir()
                source = source_fixture(kind)
                data = previous_seasons()
                other_year = copy.deepcopy(data["players"][1])
                data["players"] = [{"year": "2025", "team": profile["team"], "player": profile["player"],
                                    id_field: f"sportsnavi-{i}"} for i, profile in enumerate(source["players"])] + [other_year]
                before = copy.deepcopy(data)
                (root / "summary" / filename).write_text(json.dumps(data), encoding="utf-8")
                (root / "summary" / f"nf3_2025_{kind}.json").write_text(json.dumps(source), encoding="utf-8")
                with patch.object(integration, "ROOT", root):
                    result = integration.apply(kind)
                after = json.loads((root / "summary" / filename).read_text(encoding="utf-8"))
                self.assertEqual(after["players"][-1], other_year)
                for i, player in enumerate(after["players"][:-1]):
                    self.assertEqual(player[id_field], f"sportsnavi-{i}")
                    self.assertEqual(player["sourcePlayerId"], f"fixture:{i}")
                self.assertEqual([row for row in after["leagueStats"] if row["year"] == "2026"],
                                 [row for row in before["leagueStats"] if row["year"] == "2026"])
                for context in ("wobaConstants", "leagues"):
                    self.assertEqual([row for row in after["metricContexts"][context] if row["year"] == "2026"],
                                     [row for row in before["metricContexts"][context] if row["year"] == "2026"])
                self.assertEqual(after["sourceByYear"]["2026"], before["sourceByYear"]["2026"])
                self.assertEqual(after["sourceByYear"]["2025"]["dataset"], f"nf3_2025_{kind}.json")
                self.assertEqual(result["matched"], 12)
                self.assertEqual(result["previousRowsNotMatched"], [])

    def test_truncated_source_is_rejected_before_totals_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "summary").mkdir()
            source = source_fixture("pitchers")
            source["coverage"]["discoveredPlayers"] = 13
            path = root / "summary/player_totals.json"
            before = json.dumps(previous_seasons())
            path.write_text(before, encoding="utf-8")
            (root / "summary/nf3_2025_pitchers.json").write_text(json.dumps(source), encoding="utf-8")
            with patch.object(integration, "ROOT", root), self.assertRaisesRegex(ValueError, "Truncated source"):
                integration.apply("pitchers")
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_unmatched_published_player_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "summary").mkdir()
            source = source_fixture("pitchers")
            data = previous_seasons()
            data["players"][0].update(team="Missing team", player="Missing player")
            path = root / "summary/player_totals.json"
            before = json.dumps(data)
            path.write_text(before, encoding="utf-8")
            (root / "summary/nf3_2025_pitchers.json").write_text(json.dumps(source), encoding="utf-8")
            with patch.object(integration, "ROOT", root), self.assertRaisesRegex(ValueError, "Previously published rows missing"):
                integration.apply("pitchers")
            self.assertEqual(path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
