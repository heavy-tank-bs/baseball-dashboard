"""Independently audit published pitcher BB/HBP inning assignments."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile
import unittest

import build_pitcher_inning_walks as builder
from build_pitcher_inning_runs import normalize_team


class PublishedInningWalks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = builder.load_json(builder.ROOT / "summary/pitcher_inning_walks_2026.json")
        cls.audit = builder.load_json(builder.ROOT / "docs/pitcher-inning-walks-verification.json")
        cls.manifest = builder.load_manifest(builder.ROOT / "summary/manifest.js")
        cls.contexts = {str(row["gameId"]): row for row in builder.load_json(builder.ROOT / "summary/sportsnavi_game_context_2026.json")["games"]}
        cls.events = builder.load_json(builder.ROOT / "summary/sportsnavi_woba_events_2026.json")["events"]

    def test_all_appearances_equal_official_game_line(self):
        expected_keys = set()
        total_bb = total_hbp = 0
        for entry in self.manifest["entries"]:
            if entry["date"][:4] != "2026":
                continue
            key = f"{entry['gameId']}::{entry['team']}::{entry['pitcherId']}"
            expected_keys.add(key)
            row = self.payload["appearances"][key]
            self.assertTrue(row["verified"])
            self.assertEqual(row["walks"], int(entry["statline"]["bb"]), key)
            self.assertEqual(row["hitByPitch"], int(entry["statline"]["hbp"]), key)
            self.assertEqual(row["player"], entry["player"])
            for inning, counts in row["byInning"].items():
                self.assertIn(int(inning), range(1, 13))
                for field in ("walks", "hitByPitch", "walksAndHbp"):
                    self.assertIsInstance(counts[field], int)
                    self.assertGreaterEqual(counts[field], 0)
                self.assertEqual(counts["walksAndHbp"], counts["walks"] + counts["hitByPitch"])
            self.assertEqual(sum(counts["walks"] for counts in row["byInning"].values()), row["walks"], key)
            self.assertEqual(sum(counts["hitByPitch"] for counts in row["byInning"].values()), row["hitByPitch"], key)
            total_bb += row["walks"]
            total_hbp += row["hitByPitch"]
        self.assertEqual(expected_keys, set(self.payload["appearances"]))
        self.assertEqual(len(expected_keys), 7175)
        self.assertEqual((total_bb, total_hbp), (4841, 632))

    def test_every_inning_equals_independent_official_pa_events(self):
        expected = Counter()
        actual = Counter()
        for event in self.events:
            event_type = event["eventType"]
            if event_type not in ("uBB", "IBB", "HBP"):
                continue
            game = self.contexts[event["gameId"]]
            batting = normalize_team(event["battingTeam"])
            home, away = normalize_team(game["homeTeam"]), normalize_team(game["awayTeam"])
            self.assertIn(batting, (home, away))
            fielding = away if batting == home else home
            field = "hitByPitch" if event_type == "HBP" else "walks"
            expected[event["gameId"], fielding, int(event["inning"]), field] += 1
        for row in self.payload["appearances"].values():
            for inning, counts in row["byInning"].items():
                for field in ("walks", "hitByPitch"):
                    if counts[field]:
                        actual[row["gameId"], row["team"], int(inning), field] += counts[field]
        self.assertEqual(actual, expected)
        self.assertEqual(sum(expected.values()), 5473)

    def test_all_raw_logs_read_and_every_flow_is_unique(self):
        coverage = self.audit["coverage"]
        self.assertEqual(self.audit["problems"], [])
        self.assertEqual(coverage["unresolved"], 0)
        self.assertEqual(coverage["rawPitchRows"], 249622)
        self.assertEqual(coverage["rawTerminalWalks"], 4598)
        self.assertEqual(coverage["rawTerminalHitByPitch"], 631)
        self.assertEqual(coverage["officialEventCounts"], {"uBB": 4605, "IBB": 236, "HBP": 632})
        self.assertEqual(coverage["solutionCounts"], {"walks:unique": 1716, "hitByPitch:unique": 1716})
        # Mid-PA relief can leave the terminal walk in the reliever's raw file
        # while the official scorer charges the preceding pitcher.
        for charged, terminal, inning in (("2021039448::阪神::1600033", "2021039448::阪神::2108124", "10"),
                                           ("2021039298::中日::2100410", "2021039298::中日::1400199", "6")):
            self.assertGreater(self.payload["appearances"][charged]["byInning"][inning]["walks"], 0)
            self.assertEqual(self.payload["appearances"][terminal]["walks"], 0)
        self.assertEqual(len(self.audit["rawLogDifferences"]), 237)

    def test_rebuilding_reproduces_every_published_assignment(self):
        rebuilt, report = builder.build()
        self.assertEqual(report["problems"], [])
        self.assertEqual(rebuilt["appearances"], self.payload["appearances"])
        self.assertEqual(rebuilt["coverage"], self.payload["coverage"])


class TerminalPitchAudit(unittest.TestCase):
    def test_one_completed_walk_per_pa_and_no_annotation_inflation(self):
        entry = {"gameId": "g", "team": "オリックス", "pitcherId": "p", "player": "投手", "date": "2026-04-01",
                 "prefix": "g-p", "order": 10100, "statline": {"bb": "1", "hbp": "1", "innings": "1", "pitches": "5"}}
        pitches = [
            {"pa_index": "0110100", "seq": "1", "result": "ボール"},
            {"pa_index": "0110100", "seq": "2", "result": "四球 [敬遠ぎみ]"},
            {"pa_index": "0110200", "seq": "1", "result": "死球"},
            {"pa_index": "0110300", "seq": "1", "result": "ボール"},
            {"pa_index": "0110300", "seq": "2", "result": "見逃し"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "generated/オリックス/2026-04-01/g-p-dashboard.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"statline": entry["statline"], "pitches": pitches}), encoding="utf-8")
            rows, problems, stats = builder.read_appearances(root, [entry])
        self.assertEqual(problems, [])
        self.assertEqual(rows[0]["rawByInning"], {1: {"walks": 1, "hitByPitch": 1}})
        self.assertEqual(stats["rawTerminalWalks"], 1)
        self.assertEqual(stats["rawTerminalHitByPitch"], 1)


if __name__ == "__main__":
    unittest.main()
