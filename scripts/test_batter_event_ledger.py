"""Check official PA identity, attribution, uncertainty and count handling."""
import unittest

from batter_event_ledger import build_ledger, event_counts, log_event_type, _forced_pairs


def event(player, kind='OUT', inning=1, state='0:000', result='センターフライ'):
    return {'gameId': '1', 'date': '2026-03-27', 'battingTeam': '阪神', 'batterId': player,
            'batter': player, 'inning': inning, 'half': '表', 'eventType': kind, 'result': result, 'preState': state}


def entry(player, plates):
    return {'id': player, 'gameId': '1', 'team': '阪神', 'batterId': player,
            'dashboard': {'plateAppearances': plates}}


def plate(identifier, result='中飛', **kwargs):
    return {'id': identifier, 'result': result, 'pitchType': 'ストレート', 'speed': '150km/h',
            'pitcherHand': '右', 'balls': 1, 'strikes': 2, **kwargs}


class LedgerTests(unittest.TestCase):
    def test_pa_order_comes_from_official_events_including_ibb(self):
        rows, _ = build_ledger([entry('a', [plate('0310100')])],
                              [event('a', 'IBB', result='敬遠フォアボール'), event('a', inning=3)])
        self.assertEqual([row['paNumber'] for row in rows], [1, 2])
        self.assertIsNone(rows[0]['plate'])
        self.assertTrue(all(value is None for value in rows[0]['attributes'].values()))
        self.assertEqual(rows[1]['attributes']['speed'], 150)

    def test_incomplete_pitch_sequence_does_not_shift_later_completed_pa(self):
        rows, report = build_ledger([entry('a', [plate('0110100', 'ボール'), plate('0310100')])], [event('a', inning=3)])
        self.assertEqual(rows[0]['plate']['id'], '0310100')
        self.assertEqual(rows[0]['paNumber'], 1)
        self.assertEqual(report['ignoredLogCount'], 1)

    def test_ambiguous_repeated_batter_is_not_guessed(self):
        rows, _ = build_ledger([entry('a', [plate('0110100'), plate('0111000')])], [event('a')])
        self.assertIsNone(rows[0]['plate'])
        self.assertEqual(rows[0]['matchStatus'], 'unmatched-or-ambiguous')

    def test_crossing_alignment_has_no_forced_pair(self):
        self.assertEqual(_forced_pairs(['a','b'], ['b','a']), {})

    def test_neighboring_batters_disambiguate_repeated_batter(self):
        self.assertEqual(_forced_pairs(['a','b','a'], ['a','b']), {0: 0, 1: 1})

    def test_official_hit_correction_and_risp_override_log(self):
        rows, report = build_ledger([entry('a', [plate('0110100', '三失')])],
                                   [event('a', '1B', state='1:010', result='サードヒット')])
        self.assertEqual(rows[0]['counts']['hits'], 1)
        self.assertTrue(rows[0]['scoringPosition'])
        self.assertEqual(rows[0]['matchStatus'], 'matched-official-result-corrected')
        self.assertEqual(report['rispCorrectionCount'], 1)

    def test_unknown_velocity_and_count_remain_unknown(self):
        rows, _ = build_ledger([entry('a', [plate('0110100', speed='-', balls=None, strikes=None)])], [event('a')])
        for name in ('speed','balls','strikes'):
            self.assertIsNone(rows[0]['attributes'][name])

    def test_strikeouts_and_sacrifices_have_correct_denominators(self):
        counts = event_counts(event('a', 'OUT', result='空振り三振（振り逃げ）'))
        self.assertEqual((counts['plateAppearances'], counts['atBats'], counts['strikeouts']), (1,1,1))
        counts = event_counts(event('a', 'SH', result='ピッチャー犠牲バント'))
        self.assertEqual((counts['plateAppearances'], counts['atBats'], counts['sacBunts']), (1,0,1))
        self.assertEqual(log_event_type('捕犠野'), 'SH')
        self.assertEqual(log_event_type('一邪直'), 'OUT')

    def test_same_player_opposite_team_does_not_match(self):
        observed = entry('a', [plate('0110100')])
        observed['team'] = '巨人'
        rows, _ = build_ledger([observed], [event('a')])
        self.assertIsNone(rows[0]['plate'])

    def test_enriched_results_do_not_become_independent_evidence(self):
        observed = [entry('a', [plate('0110100', '三失')])]
        official = [event('a', '1B', state='1:010', result='サードヒット'),
                    event('a', 'IBB', inning=3, result='敬遠フォアボール')]
        original, report = build_ledger(observed, official)
        source = observed[0]['dashboard']['plateAppearances'][0]
        source.update(originalResult='三失', result='サードヒット', completed=True,
                      originalScoringPosition=False, scoringPosition=True)
        observed[0]['dashboard']['plateAppearances'].append(
            {'id': 'official-2', 'points': [], 'result': '敬遠フォアボール', 'completed': True})
        repeated, repeated_report = build_ledger(observed, official)
        self.assertEqual([r['matchStatus'] for r in original], [r['matchStatus'] for r in repeated])
        self.assertEqual(report, repeated_report)
        self.assertIsNone(repeated[1]['plate'])


if __name__ == '__main__':
    unittest.main()
