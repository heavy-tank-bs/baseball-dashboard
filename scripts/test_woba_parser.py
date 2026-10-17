"""Regression checks for PA identity, runner events and post-play states."""
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import build_woba_constants as woba

GAME = {'gameId': 'fixture', 'date': '2026-10-08', 'homeTeam': '阪神', 'awayTeam': 'ヤクルト'}


def item(player_id, state, *summaries):
    return ('<li class="bb-liveText__item"><p class="bb-liveText__batter">'
            f'<a class="bb-liveText__player" href="/npb/player/{player_id}/top">打者</a>'
            f'<span class="bb-liveText__state">{state}</span></p>'
            + ''.join(f'<p class="bb-liveText__summary">{text}</p>' for text in summaries) + '</li>')


def events(*items):
    return woba.parse_game_text(GAME, '<section class="bb-liveText"><h1 class="bb-liveText__inning">1回表</h1>' + ''.join(items) + '</section>')


class WobaParser(unittest.TestCase):
    def test_home_run_clears_original_runners(self):
        self.assertEqual(woba.post_state_from_result('ランナー三塁からホームラン 神 0-2 ヤ', (1, (False, False, True)), 'HR'), (1, (False, False, False)))

    def test_walk_forces_all_occupied_bases(self):
        self.assertEqual(woba.post_state_from_result('四球', (1, (True, True, False)), 'uBB'), (1, (True, True, True)))

    def test_scoring_sacrifice_does_not_retain_leading_preplay_runner(self):
        self.assertEqual(woba.post_state_from_result('0アウト三塁から犠飛 神 0-1 ヤ 1アウト', (0, (False, False, True)), 'SF', 1), (1, (False, False, False)))

    def test_failed_bunt_and_safety_bunt(self):
        self.assertEqual(woba.classify_event('送りバントを試みるもダブルプレー 2アウト'), 'OUT')
        self.assertEqual(woba.classify_event('送りバント失敗 1アウト'), 'OUT')
        self.assertEqual(woba.classify_event('見事送りバントを決める 1アウト二塁'), 'SH')
        self.assertEqual(woba.classify_event('セーフティバントを決める 一塁'), '1B')

    def test_final_annotation_does_not_replace_completed_pa(self):
        result = events(item('1', '二死走者なし', '空振り三振 3アウト', '試合終了'))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['eventType'], 'OUT')
        self.assertEqual(result[0]['preState'], '2:000')
        self.assertEqual(result[0]['postState'], '3:000')

    def test_fielding_error_after_hit_preserves_hit_and_advance(self):
        result = events(item('1', '無死走者なし', 'ライトへのヒット 一塁', '外野手 (右):ファンブル 二塁'))
        self.assertEqual(result[0]['eventType'], '1B')
        self.assertEqual(result[0]['postState'], '0:010')

    def test_inning_ending_runner_out_is_not_a_pa(self):
        self.assertEqual(events(item('1', '二死一塁', '一塁走者:盗塁を試みるもアウト 3アウト')), [])

    def test_next_batter_start_does_not_include_mid_pa_steal(self):
        result = events(item('1', '無死走者なし', 'ライトへのヒット 一塁'),
                        item('2', '無死一塁', '一塁走者:盗塁成功 二塁', '空振り三振 1アウト'))
        self.assertEqual(result[0]['postState'], '0:100')
        self.assertEqual(result[1]['plateAppearancePreState'], '0:100')
        self.assertEqual(result[1]['preState'], '0:010')

    def test_fc_error_and_uncaught_third_strike_are_ab_events(self):
        self.assertEqual(woba.classify_event('遊撃手のフィルダースチョイスによりオールセーフ 一二塁'), 'OUT')
        self.assertEqual(woba.classify_event('三塁手のファンブルにより出塁する 一塁'), 'ROE')
        self.assertEqual(woba.classify_event('捕逸による振り逃げ 一塁'), 'OUT')

    def test_squeeze_hit_sacrifice_and_sacrifice_fielder_choice(self):
        self.assertEqual(woba.classify_event('ランナー一三塁からスクイズ成功 神 0-1 ヤ 一二塁', (1, (True, False, True))), '1B')
        self.assertEqual(woba.classify_event('スクイズ成功 神 0-1 ヤ 2アウト三塁', (1, (True, False, True))), 'SH')
        self.assertEqual(woba.classify_event('スクイズ成功！投手のフィルダースチョイスにより出塁 一二塁'), 'SH')

    def test_foul_error_does_not_replace_later_walk(self):
        result = events(item('1', '二死走者なし', '捕手:ファウルフライを落球', '四球を選ぶ 一塁'))
        self.assertEqual(result[0]['eventType'], 'uBB')

    def test_incomplete_pa_on_runner_baserunning_out(self):
        self.assertEqual(events(item('1', '二死一二塁', '二塁走者は走塁死 3アウト')), [])

    def test_mid_pa_pinch_hitter_receives_walk(self):
        markup = item('1', '無死走者なし', '四球を選ぶ 一塁')
        markup = markup.replace('</p>', '</p><p class="bb-liveText__batter"><a class="bb-liveText__player" href="/npb/player/2/top">代打</a><span class="bb-liveText__state">無死走者なし</span></p>', 1)
        self.assertEqual(events(markup)[0]['batterId'], '2')

    def test_interference_is_a_pa_but_not_a_woba_denominator_event(self):
        result = events(item('1', '無死走者なし', '打撃妨害により出塁する 一塁'))
        self.assertEqual(result[0]['eventType'], 'INT')
        self.assertEqual(result[0]['postState'], '0:100')
        self.assertNotIn('INT', woba.DENOMINATOR_EVENTS)

    def test_woba_scale_target_excludes_intentional_walks(self):
        # Two unintentional on-base events in four eligible PA. IBB, SH and
        # interference do not change the target OBP or wOBA denominator.
        sample = [{'eventType': category, 'preState': '2:000', 'postState': '3:000',
                   'inningRuns': 0, 'runsBefore': 0, 'runsOnPlay': 0, 'date': '2026-10-08'}
                  for category in ('1B', 'uBB', 'OUT', 'SF', 'IBB', 'SH', 'INT')]
        constants = woba.calculate_constants_for_year('2026', sample)
        self.assertEqual(constants['denominator'], 4)
        self.assertEqual(constants['leagueObp'], 0.5)
        self.assertEqual(constants['missingRunValueCounts'], {})


class PublicationCompleteness(unittest.TestCase):
    def _inputs(self, directory):
        path = Path(directory)
        entries = [{'gameId': 'early', 'date': '2026-03-27'},
                   {'gameId': 'late', 'date': '2026-10-08'}]
        (path / 'manifest.js').write_text('window.MANIFEST = ' + json.dumps({'entries': entries}) + ';', encoding='utf-8')
        (path / 'context_2026.json').write_text(json.dumps({'games': entries[:1]}), encoding='utf-8')
        return path

    def test_missing_context_is_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._inputs(directory)
            with patch.object(woba, 'SUMMARY_DIR', path), patch.object(woba, 'CONTEXT_TEMPLATE', path / 'context_{season}.json'), patch.object(woba, 'fetch_with_retry') as fetch:
                with self.assertRaisesRegex(RuntimeError, 'missing game IDs.*late'):
                    woba.build_for_season('2026', delay_seconds=0)
                fetch.assert_not_called()

    def test_date_cutoff_requires_only_selected_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._inputs(directory)
            with patch.object(woba, 'SUMMARY_DIR', path), patch.object(woba, 'CONTEXT_TEMPLATE', path / 'context_{season}.json'), patch.object(woba, 'fetch_with_retry', return_value='fixture'), patch.object(woba, 'parse_game_text', return_value=[{'gameId': 'early'}]), patch.object(woba, 'calculate_constants_for_year', return_value={}):
                constants, parsed = woba.build_for_season('2026', through_date='2026-04-01', delay_seconds=0)
                self.assertEqual(constants['games'], 1)
                self.assertEqual(parsed, [{'gameId': 'early'}])

    def test_partial_run_does_not_overwrite_complete_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            constants_path = path / 'woba_constants.json'
            original = json.dumps({'byYear': {'2026': {'coverageComplete': True, 'games': 858, 'expectedGames': 858}}})
            constants_path.write_text(original, encoding='utf-8')
            events_path = path / 'events_2026.json'
            events_path.write_text('original events', encoding='utf-8')
            with patch.object(woba, 'CONSTANTS_PATH', constants_path), patch.object(woba, 'EVENTS_TEMPLATE', path / 'events_{season}.json'), patch.object(woba, 'build_for_season', return_value=({'games': 100}, [])), patch('sys.argv', ['build_woba_constants.py', '--season', '2026', '--through-date', '2026-05-01']):
                with self.assertRaisesRegex(RuntimeError, 'Refusing to replace the complete'):
                    woba.main()
            self.assertEqual(constants_path.read_text(encoding='utf-8'), original)
            self.assertEqual(events_path.read_text(encoding='utf-8'), 'original events')


if __name__ == '__main__':
    unittest.main()
