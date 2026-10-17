"""Regression fixtures for batting slots separated by substitute rows.

Source formats checked against NPB 2026/1006/t-c-24/box.html and SportsNavi
game 2021038761/stats. SportsNavi's first column is position, with its explicit
'（）:先発' legend; NPB's first column supplies numbered starting slots.
"""
import argparse
import ast
from collections import defaultdict
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest

from npb_boxscore_stats import parse_boxscore

ROOT = Path(__file__).resolve().parent.parent


def lineup(base=0):
    rows = []
    for slot in range(1, 10):
        rows.append((slot, base + slot, True))
        if slot in (2, 3):
            rows.extend([(slot, base + slot * 10, False), (slot, base + slot * 10 + 1, False)])
    return rows


def npb_fixture(first_label=None):
    html, lookup = [], {}
    for side, team, base in [('t', '阪神タイガース', 0), ('b', '広島東洋カープ', 100)]:
        rows = []
        for index, (slot, player, starter) in enumerate(lineup(base)):
            lookup[('npb', str(player))] = str(player)
            lookup[('npb_name', str(player))] = f'Player {player}'
            label = str(slot) if starter else ''
            if first_label is not None and index == 0:
                label = first_label
            cells = [label, '(三)' if starter else '打', f'<a href="/bis/players/{player}.html">P{player}</a>'] + ['0'] * 5 + ['-']
            rows.append('<tr>' + ''.join(f'<td>{value}</td>' for value in cells) + '</tr>')
        headers = ['', '守備', '選手', '打数', '得点', '安打', '打点', '盗塁', '1']
        batting = (f'<table id="tablefix_{side}_b"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers)
                   + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')
        pitching_cells = ['', f'<a href="/bis/players/{base + 1}.html">P</a>'] + ['0'] * 12
        pitching = (f'<table id="tablefix_{side}_p"><tbody><tr>'
                    + ''.join(f'<td>{v}</td>' for v in pitching_cells) + '</tr></tbody></table>')
        html.append(f'<section><h4>{team}</h4>{batting}{pitching}</section>')
    return ''.join(html), lookup


def sportsnavi_parser():
    # Load the production parsing function without importing dashboard chart
    # libraries; only BeautifulSoup is needed for these HTML parser fixtures.
    from bs4 import BeautifulSoup
    source = ast.parse((ROOT / 'summary/build_manifest.py').read_text(encoding='utf-8'))
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'parse_game_batting_stats_from_html')
    namespace = {'BeautifulSoup': BeautifulSoup, 're': re,
                 'text': lambda n: n.get_text(' ', strip=True) if n is not None else '',
                 'normalize_matchup_team_name': lambda name: name,
                 'parse_int': lambda value: int(value or 0),
                 'DASHBOARD': SimpleNamespace()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'build_manifest.py', 'exec'), namespace)
    return namespace[function.name]


def sportsnavi_fixture(first_position=None, brackets=('(', ')')):
    headers = ['位置', '選手名', '打率', '打数', '得点', '安打', '打点', '三振',
               '四球', '死球', '犠打', '盗塁', '失策', '本塁打', '1回']
    rows = []
    for index, (slot, player, starter) in enumerate(lineup()):
        position = brackets[0] + '三' + brackets[1] if starter else '打三'
        if first_position is not None and index == 0:
            position = first_position
        name = f'<a href="/npb/player/{player}/top">Player {player}</a>'
        cells = [position, name, '.000'] + ['0'] * 11 + ['']
        rows.append('<tr>' + ''.join(f'<td>{value}</td>' for value in cells) + '</tr>')
    return ('<table class="bb-teamScoreTable"><tr><td>阪神</td></tr></table>'
            '<table class="bb-statsTable"><tr>' + ''.join(f'<th>{h}</th>' for h in headers)
            + '</tr>' + ''.join(rows) + '</table>')


class NpbBattingOrder(unittest.TestCase):
    def test_numbered_slots_survive_multiple_substitutes(self):
        batting, _ = parse_boxscore(*npb_fixture())
        players = batting['阪神']
        self.assertEqual((players['4']['order'], players['4']['battingOrder'], players['4']['isStarter']), (8, 4, True))
        self.assertEqual((players['20']['battingOrder'], players['20']['isStarter']), (2, False))
        self.assertEqual((players['21']['battingOrder'], players['21']['isStarter']), (2, False))
        self.assertEqual(players['9']['battingOrder'], 9)
        self.assertEqual(sum(p['isStarter'] for key, p in players.items() if key == p['playerId']), 9)

    def test_missing_preceding_slot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Substitute without'):
            parse_boxscore(*npb_fixture(first_label=''))

    def test_nonsequential_slot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid batting-order'):
            parse_boxscore(*npb_fixture(first_label='2'))


class SportsNaviBattingOrder(unittest.TestCase):
    def test_position_parentheses_identify_starters(self):
        players = sportsnavi_parser()(sportsnavi_fixture())['阪神']
        self.assertEqual((players['4']['order'], players['4']['battingOrder'], players['4']['isStarter']), (8, 4, True))
        self.assertEqual((players['20']['battingOrder'], players['20']['isStarter']), (2, False))
        self.assertEqual(players['9']['battingOrder'], 9)
        self.assertEqual(sum(p['isStarter'] for key, p in players.items() if key == p['playerId']), 9)

    def test_fullwidth_parentheses(self):
        self.assertTrue(sportsnavi_parser()(sportsnavi_fixture(brackets=('（', '）')))['阪神']['4']['isStarter'])

    def test_substitute_before_first_starter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid SportsNavi'):
            sportsnavi_parser()(sportsnavi_fixture(first_position='打'))

    def test_sacrifice_fly_is_stored_for_official_splits(self):
        html = sportsnavi_fixture().replace('<td></td></tr>', '<td><span class="bb-statsTable__dataDetail">中犠飛</span></td></tr>', 1)
        player = sportsnavi_parser()(html)['阪神']['1']
        self.assertEqual(player['sacFlies'], 1)
        self.assertEqual(player['plateAppearances'], 1)


class OfficialOrderSplits(unittest.TestCase):
    def builder(self):
        source = ast.parse((ROOT / 'summary/build_manifest.py').read_text(encoding='utf-8'))
        names = {'build_batter_order_splits', 'build_batter_split_bucket', 'finalize_batter_split_bucket'}
        nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {'defaultdict': defaultdict, 'parse_int': lambda value: int(value or 0),
                     'annual_player_key': lambda year, player_id, team, name: player_id,
                     'round_or_none': lambda value, digits: round(value, digits) if value is not None else None}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'build_manifest.py', 'exec'), namespace)
        return namespace['build_batter_order_splits']

    def test_uses_official_counts_when_pitch_logs_are_incomplete(self):
        entries = [{'date': '2026-10-06', 'gameId': 'game', 'team': '阪神', 'batterId': '4',
                    'player': '佐藤', 'order': 8, 'dashboard': {'plateAppearances': []}}]
        stats = dict(player='佐藤', playerId='4', battingOrder=4, isStarter=True, plateAppearances=5, ab=4, hits=1,
                     singles=1, doubles=0, triples=0, homeRuns=0, walks=0, hitByPitch=0,
                     sacBunts=0, sacFlies=1, strikeouts=1)
        result = self.builder()(entries, {'game': {'阪神': {'4': stats}}})[('2026', '4')]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], '4番')
        self.assertEqual((result[0]['atBats'], result[0]['hits'], result[0]['sacFlies']), (4, 1, 1))
        self.assertEqual(result[0]['battingAverage'], .250)

    def test_includes_official_ibb_without_any_batter_entry(self):
        entries = [{'date': '2026-10-06', 'gameId': 'game', 'team': '阪神', 'batterId': '4', 'player': '佐藤'}]
        stats = dict(player='代打', playerId='5', battingOrder=7, isStarter=False, plateAppearances=1,
                     ab=0, hits=0, singles=0, doubles=0, triples=0, homeRuns=0, walks=1,
                     hitByPitch=0, sacBunts=0, sacFlies=0, strikeouts=0)
        result = self.builder()(entries, {'game': {'阪神': {'5': stats}}})[('2026', '5')]
        self.assertEqual(result[0]['label'], '7番')
        self.assertEqual((result[0]['plateAppearances'], result[0]['walks']), (1, 1))
        self.assertIsNone(result[0]['battingAverage'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--npb-only', action='store_true', help='Run dependency-free NPB tests only')
    parser.add_argument('--deps', type=Path, help='Existing dependency directory containing BeautifulSoup')
    args, remaining = parser.parse_known_args()
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve()))
    suite = unittest.TestLoader().loadTestsFromTestCase(NpbBattingOrder) if args.npb_only else unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
