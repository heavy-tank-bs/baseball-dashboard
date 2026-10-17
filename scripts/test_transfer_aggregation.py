"""Regression checks for cross-league and same-league annual aggregates."""
import copy
import unittest
from rebuild_annual_totals import load_builder, preserve_other_years

m = load_builder()


def appearance(team, date, gid):
    return {"id": gid, "gameId": gid, "date": date, "team": team,
            "league": m.team_league(team), "pitcherId": "test", "batterId": "test",
            "player": "Test Player", "uniformNumber": "99" if date.endswith("02") else "1",
            "statline": {"innings": "1", "pitches": "12", "k": "1", "bb": "1"},
            "dashboard": {}, "_pitchRows": []}


class Transfers(unittest.TestCase):
    def test_pitcher_cross_league(self):
        entries = [appearance("DeNA", "2026-06-01", "one"), appearance("ソフトバンク", "2026-06-02", "two")]
        result = m.build_player_totals(entries, {}, {})["players"]
        self.assertEqual({r["team"] for r in result}, {"DeNA", "ソフトバンク"})
        self.assertEqual(sum(r["inningsOuts"] for r in result), 6)
        self.assertEqual(len({r["aggregationKey"] for r in result}), 2)
        for r in result:
            self.assertEqual(r["games"], 1)
            self.assertEqual(r["monthlySplits"][0]["games"], 1)
            self.assertEqual(r["league"], m.team_league(r["team"]))

    def test_same_league_latest_team_independent_of_input_order(self):
        entries = [appearance("西武", "2026-06-02", "two"), appearance("日本ハム", "2026-06-01", "one")]
        for sequence in (entries, list(reversed(entries))):
            result = m.build_player_totals(sequence, {}, {})["players"]
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["team"], "西武")
            self.assertEqual(result[0]["teams"], ["西武"])
            self.assertEqual(result[0]["games"], 2)
            self.assertEqual(result[0]["uniformNumber"], "99")
            self.assertEqual(result[0]["monthlySplits"][0]["team"], "西武")

    def test_batter_cross_league_and_same_league(self):
        for team, expected in (("ソフトバンク", 2), ("巨人", 1)):
            entries = [appearance("DeNA", "2026-06-01", "one"), appearance(team, "2026-06-02", "two")]
            stats = {e["gameId"]: {e["team"]: {"test": {"playerId": "test", "player": "Test Player", "ab": 3, "hits": 1, "singles": 1, "plateAppearances": 4, "walks": 1}}} for e in entries}
            rows = m.build_batter_totals(entries, stats, entries, {}, {})["players"]
            self.assertEqual(len(rows), expected)
            self.assertEqual(sum(r["atBats"] for r in rows), 6)
            self.assertEqual(sum(r["walks"] for r in rows), 2)
            self.assertEqual(sum(r["games"] for r in rows), 2)
            if expected == 1:
                self.assertEqual(rows[0]["team"], "巨人")
            for row in rows:
                self.assertEqual(sum(s["atBats"] for s in row["monthlySplits"]), row["atBats"])

    def test_three_teams_cross_league_keeps_each_team(self):
        entries = [appearance(team, f"2026-06-0{i}", str(i)) for i, team in enumerate(("DeNA", "巨人", "西武"), 1)]
        rows = m.build_player_totals(entries, {}, {})["players"]
        self.assertEqual(len(rows), 3)

    def test_preserve_historical_season(self):
        old = {"years": ["2025", "2026"], "players": [{"year": "2025", "games": 10}]}
        new = {"years": ["2026"], "players": []}
        result = preserve_other_years(new, old)
        self.assertEqual(result["players"], old["players"])


if __name__ == "__main__":
    unittest.main()
