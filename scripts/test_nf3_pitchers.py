"""Focused structural checks for the nf3 2025 pitcher archive (no network)."""
import json
from pathlib import Path
import unittest

from bs4 import BeautifulSoup

from collect_nf3_pitchers import expand_rows, outs, parse_tables


class Nf3PitcherTests(unittest.TestCase):
    def test_span_alignment(self):
        soup = BeautifulSoup("""<table><tr><th rowspan=2>QS率</th><th colspan=3>QS時勝敗</th></tr>
        <tr><th>勝</th><th>敗</th><th>勝敗無</th></tr></table>""", "html.parser")
        self.assertEqual(expand_rows(soup.find_all("tr")), [
            ["QS率", "QS時勝敗", "QS時勝敗", "QS時勝敗"],
            ["QS率", "勝", "敗", "勝敗無"],
        ])

    def test_repeated_bands_preserve_header_value_pairs(self):
        soup = BeautifulSoup("""<table class=Base_P><caption>通算成績</caption>
        <tr><th>防御率</th><th>試合</th></tr><tr><td>2.39</td><td>23</td></tr>
        <tr><th>回数</th><th>投球数</th></tr><tr><td>150.1</td><td>2403</td></tr></table>""", "html.parser")
        tables = parse_tables(soup)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[1]["title"], "通算成績（2）")
        self.assertEqual(tables[1]["headers"], ["回数", "投球数"])
        self.assertEqual(tables[1]["rows"], [["150.1", "2403"]])

    def test_baseball_innings(self):
        self.assertEqual(outs("150.1"), 451)
        with self.assertRaises(ValueError):
            outs("150.3")

    def test_published_archive(self):
        path = Path(__file__).resolve().parents[1] / "summary/nf3_2025_pitchers.json"
        if not path.exists():
            self.skipTest("Run collect_nf3_pitchers.py to create the full archive")
        data = json.loads(path.read_text(encoding="utf-8"))
        coverage = data["coverage"]
        self.assertEqual(coverage["teams"], 12)
        self.assertGreaterEqual(coverage["collectedPlayers"], 350)
        self.assertEqual(coverage["discoveredPlayers"], coverage["collectedPlayers"])
        self.assertFalse(coverage["parseFailures"])
        self.assertFalse(coverage["issues"])
        self.assertEqual(len({p["nf3Id"] for p in data["players"]}), len(data["players"]))
        for player in data["players"]:
            with self.subTest(player=player["nf3Id"]):
                annual = player["annual"]
                self.assertEqual(annual["strikeouts"], annual["swingingStrikeouts"] + annual["lookingStrikeouts"])
                self.assertEqual(annual["hits"], annual["singles"] + annual["doubles"] + annual["triples"] + annual["homeRuns"])
                self.assertEqual(annual["walks"], annual["unintentionalWalks"] + annual["intentionalWalks"])
                self.assertEqual(sum(x["inningsOuts"] for x in annual["monthlySplits"]), annual["inningsOuts"])
                for table in player["tables"]:
                    self.assertTrue(table["title"])
                    self.assertTrue(table["headers"])
                    self.assertTrue(all(len(row) == len(table["headers"]) for row in table["rows"]))
        miyagi = next(p for p in data["players"] if p["nf3Id"] == "B:18")
        self.assertEqual(miyagi["annual"]["pitches"], 2403)
        self.assertEqual(miyagi["annual"]["atBats"], 571)
        self.assertEqual(miyagi["annual"]["qualityStarts"], 18)


if __name__ == "__main__":
    unittest.main()
