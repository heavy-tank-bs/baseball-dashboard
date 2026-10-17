"""Focused regression tests for pitcher PA classification and split denominators.

AST loading keeps these fixtures independent of plotting/network dependencies.
"""
import ast
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent.parent


def functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(**namespace)


ns = {'HIT_WORDS': ('安',), 'STRIKEOUT_WORDS': ('三振', '振逃'), 'GROUNDER_WORDS': ('ゴロ', '併打'),
      'FLY_WORDS': ('飛', '直', 'ライナー'), 'SWING_MISS_WORDS': ('空振り', '空三振', 'バ三振', '振逃'),
      'np': SimpleNamespace(mean=lambda a: sum(a) / len(a)), 'defaultdict': defaultdict, 'Counter': Counter,
      'COUNT_BUCKETS': ('初球', '追い込み前', '2ストライク以降', 'フルカウント', '不明')}
DASHBOARD = functions('scripts/build_dashboard.py', [
    'is_ab_result', 'classify_terminal_result', 'normalize_result', 'classify_hit_type',
    'classify_plate_appearance_result', 'build_stat_bucket', 'record_ab_result', 'summarize_stat_row',
    'parse_speed', 'parse_inning', 'is_swing_miss_result', 'build_plate_appearances', 'safe_int',
    'build_count_mix_summary', 'classify_count_bucket', 'advance_count'], ns)
env = {'DASHBOARD': DASHBOARD, 'defaultdict': defaultdict, 'Counter': Counter,
       'INNING_SLOTS': list(range(1, 13)), 'HEATMAP_WIDTH': 54.0, 'HEATMAP_HEIGHT': 63.0,
       'parse_int': lambda v: int(v or 0), 'parse_float': lambda v: None if v is None else float(v),
       'round_or_none': lambda v, n: round(v, n) if v is not None else None,
       'outs_to_ip': lambda n: n / 3, 'outs_to_innings_notation': lambda n: f'{n // 3}.{n % 3}'}
M = functions('summary/build_manifest.py', [
    'serialize_stat_summary', 'build_inning_summary', 'build_plate_discipline_bucket',
    'record_plate_discipline_pitch', 'finalize_plate_discipline_bucket', 'is_located_pitch',
    'is_zone_pitch', 'is_called_strike_result', 'is_ball_result', 'is_contact_result', 'is_swing_result',
    'add_pitcher_source_coverage', 'pitcher_source_is_complete', 'build_pitcher_game_split_bucket',
    'finalize_pitcher_game_split_bucket', 'classify_outcome_result'], env)


class PitcherAggregates(unittest.TestCase):
    def test_outcome_records_sacrifice_fielders_choice_and_uncaught_third_strike(self):
        self.assertEqual(M.classify_outcome_result('投犠野'), 'sacrificeBunts')
        self.assertEqual(M.classify_outcome_result('振逃'), 'swingingStrikeouts')
        self.assertIsNone(M.classify_outcome_result('ボール'))

    def test_partial_pa_count_is_unknown(self):
        rows = [{'seq': '3', 'pitchType': '直球', 'result': 'ファウル'},
                {'seq': '4', 'pitchType': '直球', 'result': '右安'}]
        _, totals = DASHBOARD.build_count_mix_summary({'one': rows})
        self.assertEqual(totals['不明'], 2)
        self.assertEqual(totals['初球'], 0)

    def test_non_pa_results_do_not_count_as_at_bats(self):
        for text in ('ボール', 'ファウル', '空振り', '見逃し', '二盗失敗', 'けん制死', '打撃妨害', '捕妨', '敬遠', '投犠野', '一犠失', '不明'):
            with self.subTest(result=text):
                self.assertFalse(DASHBOARD.is_ab_result(text))
        self.assertEqual(DASHBOARD.classify_terminal_result('不明'), 'UNKNOWN')

    def test_completed_pa_results(self):
        for text, category in [('左安', '1B'), ('右２', '2B'), ('中本', 'HR'), ('空三振', 'K'), ('二併打', 'OUT'), ('三失', 'OUT'), ('中犠飛', 'SF')]:
            self.assertEqual(DASHBOARD.classify_terminal_result(text), category)
        bucket = DASHBOARD.build_stat_bucket()
        for result in ('ボール', '投犠野', '捕妨', '右安', '空三振'):
            DASHBOARD.record_ab_result(bucket, result)
        self.assertEqual((bucket['ab'], bucket['hits'], bucket['strikeouts']), (2, 1, 1))

    def test_inning_split_keeps_discipline_and_sacrifice_fly(self):
        rows = [{'pa_index': f'0100{i}', 'seq': 1, 'pitchType': '直球', 'result': result,
                 'speed': '145km/h', 'left': x, 'top': 30}
                for i, (result, x) in enumerate([('見逃し', 25), ('空三振', 50), ('中犠飛', 25), ('右安', 25)])]
        first = M.build_inning_summary(rows, ['直球'])['all'][0]
        self.assertEqual(first['sacrificeFlies'], 1)
        self.assertEqual(first['atBats'], 2)
        self.assertEqual(first['swingCount'], 3)
        self.assertEqual(first['calledStrikeCount'], 1)
        self.assertEqual(first['zoneCount'], 3)
        self.assertEqual(first['whiffRate'], 33.3)
        self.assertEqual(first['csw'], 50.0)

    def test_incomplete_source_does_not_mix_official_hits_with_partial_ab(self):
        bucket = M.build_pitcher_game_split_bucket('test')
        bucket.update(outs=3, hits=2, atBats=2)
        M.add_pitcher_source_coverage(bucket, {'sourceCoverage': {'complete': False}})
        result = M.finalize_pitcher_game_split_bucket(bucket)
        self.assertIsNone(result['battingAverageAllowed'])
        self.assertIsNone(result['babipAllowed'])
        self.assertEqual(result['hits'], 2)
        self.assertEqual(result['sourceCoverage']['incompleteGames'], 1)


if __name__ == '__main__':
    unittest.main()
