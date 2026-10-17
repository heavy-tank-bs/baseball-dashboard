"""Regression checks for official play-by-play state and run attribution."""
import unittest

from npb_woba_events import parse_game_text


LOOKUP = {("npb", "1"): "sports1", ("npb_name", "1"): "Test Batter"}


def row(outs, bases, result, batter=True):
    name = '<a href="/bis/players/1.html">Test</a>' if batter else ""
    return f'<table><tr><td>{outs}アウト</td><td>{bases}</td><td>{name}</td><td>0-0より</td><td>{result}</td></tr></table>'


def parse(rows, runs=0):
    game = {"gameId": "1", "date": "2026-10-08", "homeTeam": "阪神", "awayTeam": "ヤクルト",
            "inningScores": {"away": {"innings": [{"inning": 1, "runs": runs}]}}}
    return parse_game_text(game, '<h5>1回表（ヤクルトの攻撃）</h5>' + ''.join(rows), LOOKUP)


class OfficialEventsTest(unittest.TestCase):
    def test_runner_score_does_not_belong_to_next_batter(self):
        events = parse([row(0, '', 'スリーベース'), row(0, '3塁', '暴投', False),
                        row(0, '', 'センターフライ'), row(1, '', '三振'), row(2, '', '三振')], 1)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0]['runsOnPlay'], 0)
        self.assertEqual(events[0]['postState'], '0:001')
        self.assertEqual(events[1]['runsBefore'], 1)
        self.assertEqual(events[1]['runsOnPlay'], 0)

    def test_third_out_strands_runners(self):
        events = parse([row(0, '', 'フォアボール'), row(0, '1塁', '三振'),
                        row(1, '1塁', '三振'), row(2, '1塁', '三振')])
        self.assertEqual(events[-1]['postState'], '3:000')
        self.assertEqual(events[-1]['runsOnPlay'], 0)

    def test_double_play_and_non_rbi_error_score(self):
        events = parse([row(0, '', 'スリーベース'), row(0, '3塁', 'ショートエラー'),
                        row(0, '1塁', 'ショートゴロ併殺打'), row(2, '', '三振')], 1)
        self.assertEqual(events[1]['eventType'], 'ROE')
        self.assertEqual(events[1]['runsOnPlay'], 1)
        self.assertEqual(events[2]['postState'], '2:000')

    def test_walkoff_ends_run_expectancy(self):
        events = parse([row(0, '', 'ツーベース'), row(0, '2塁', 'センター前ヒット')], 1)
        self.assertEqual(events[-1]['runsOnPlay'], 1)
        self.assertEqual(events[-1]['postState'], '3:000')

    def test_sacrifice_bunt_classification(self):
        events = parse([row(0, '', 'フォアボール'), row(0, '1塁', 'ピッチャー犠牲バント'),
                        row(1, '2塁', '三振'), row(2, '2塁', '三振')])
        self.assertEqual(events[1]['eventType'], 'SH')

    def test_invalid_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Impossible run transition'):
            parse([row(0, '', '三振'), row(1, '1塁', '三振')])

    def test_html_line_score_overrides_stale_context(self):
        game = {"gameId": "1", "homeTeam": "阪神", "awayTeam": "ヤクルト"}
        html = '<table id="tablefix_ls"><tr class="bottom"><th>阪神</th><td>1x</td><td class="total-1">1</td></tr></table>'
        html += '<h5>1回裏（阪神の攻撃）</h5>' + row(0, '', 'ホームラン')
        events = parse_game_text(game, html, LOOKUP)
        self.assertEqual(events[0]['runsOnPlay'], 1)
        self.assertEqual(events[0]['terminalReason'], 'walkoff')

    def test_incomplete_batter_does_not_count_as_pa(self):
        events = parse([row(0, '', '三振'), row(1, '', '三振'), row(2, '', 'フォアボール'),
                        row(2, '1塁', '二塁盗塁失敗', False), row(2, '1塁', '（途中終了）')])
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]['postState'], '2:100')

    def test_strikeout_and_caught_stealing_share_source_state(self):
        events = parse([row(0, '', 'フォアボール'), row(0, '1塁', '空振り三振'),
                        row(0, '1塁', '二塁盗塁失敗', False), row(2, '', '三振')])
        self.assertEqual(events[1]['runsOnPlay'], 0)
        self.assertEqual(events[1]['postState'], '1:100')
        self.assertEqual(events[2]['preState'], '2:000')

    def test_rain_called_during_first_uncompleted_pa(self):
        self.assertEqual(parse([row(0, '', '（途中終了）')]), [])
        with self.assertRaisesRegex(ValueError, 'Empty inning'):
            parse([row(0, '', '（途中終了）')], runs=1)


if __name__ == '__main__':
    unittest.main()
