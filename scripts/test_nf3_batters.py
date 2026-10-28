"""Regression checks for nf3's styled summaries and grouped table headers."""
import unittest

from bs4 import BeautifulSoup
from collect_nf3_batters import parse_listing, table_blocks


class Nf3BatterTables(unittest.TestCase):
    def table(self, html):
        return BeautifulSoup(html, "html.parser").table

    def test_numeric_index2_row_is_data(self):
        blocks = table_blocks(self.table("""<table><caption>ランナ−別成績</caption>
          <tr class=Index><th>条件</th><th>打率</th><th>打数</th><th>安打</th></tr>
          <tr><th>無し</th><td>.250</td><td>4</td><td>1</td></tr>
          <tr class=Index2><th>得点圏</th><th>.400</th><th>5</th><th>2</th></tr></table>"""))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["rows"][-1], ["得点圏", ".400", "5", "2"])

    def test_grouped_headers_expand_rowspan_and_colspan(self):
        blocks = table_blocks(self.table("""<table><caption>起用一覧</caption>
          <tr class=Index><th rowspan=2>試合</th><th colspan=2>先発</th></tr>
          <tr class=Index2><th>右</th><th>左</th></tr>
          <tr><td>3</td><td>2</td><td>1</td></tr></table>"""))
        self.assertEqual(blocks[0]["headers"], ["試合", "先発 / 右", "先発 / 左"])
        self.assertEqual(blocks[0]["rows"], [["3", "2", "1"]])

    def test_repeated_annual_sections_are_independent(self):
        blocks = table_blocks(self.table("""<table><caption>通算成績</caption>
          <tr class=Index><th>試合</th><th>打数</th></tr><tr><td>3</td><td>10</td></tr>
          <tr class=Index><th>四球</th><th>敬遠</th></tr><tr><td>2</td><td>1</td></tr></table>"""))
        self.assertEqual([b["title"] for b in blocks], ["通算成績（1）", "通算成績（2）"])
        self.assertEqual(blocks[1]["headers"], ["四球", "敬遠"])

    def test_listing_total_colspan_and_discovered_zero_pa_player(self):
        html = """<table><tr class=Index><th>背番</th><th>名前</th><th>席</th>
          <th>試合</th><th>打席</th><th>打数</th><th>安打</th></tr>
          <tr class=Index2><th colspan=3>合計</th><th>143</th><th>10</th><th>9</th><th>3</th></tr>
          <tr><td>12</td><td><a href='./Pacific/B/f/12_stat.htm'>選手</a></td><td>右</td>
          <td>2</td><td>0</td><td>0</td><td>0</td></tr></table>"""
        players, total = parse_listing(html, "B", "オリックス", "パ")
        self.assertEqual(total["plateAppearances"], 10)
        self.assertEqual(players[0]["sourceUrl"], "https://nf3.sakura.ne.jp/2025/Pacific/B/f/12_stat.htm")
        self.assertEqual(players[0]["listingAnnual"]["games"], 2)
        self.assertEqual(players[0]["listingAnnual"]["plateAppearances"], 0)

    def test_listing_discovers_transfer_basename_and_retains_listing_number(self):
        html = """<table><tr class=Index><th>背番</th><th>名前</th><th>席</th>
          <th>試合</th><th>打席</th><th>打数</th><th>安打</th></tr>
          <tr class=Index2><th colspan=3>合計</th><th>143</th><th>10</th><th>9</th><th>3</th></tr>
          <tr><td>55</td><td><a href='./Central/G/f/tr_H_55_stat.htm'>秋広優人</a></td><td>左</td>
          <td>7</td><td>8</td><td>7</td><td>1</td></tr></table>"""
        players, _ = parse_listing(html, "G", "巨人", "セ")
        self.assertEqual(players[0]["nf3Id"], "G:tr_H_55")
        self.assertEqual(players[0]["uniformNumber"], "55")


if __name__ == "__main__":
    unittest.main()
