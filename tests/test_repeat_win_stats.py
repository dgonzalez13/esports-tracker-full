import unittest
from datetime import datetime, timezone
from tests import test_six_match_stats
from six_match_stats import calculate_six_match_stats
from web_tracker.generate_site import render_repeat_win_stats, render_active_repeat_matches


class RepeatWinTests(unittest.TestCase):
    def test_active_condition_accounts_for_matches_since_single_win(self):
        payload = self.stats('VDDDVD')
        row = next(r for r in payload['active_repeat_rows'] if r['band'] == '>40%' and r['played'] == 3 and r['win_position'] == 1)
        self.assertEqual(row['sample'], 1)
        self.assertEqual(row['next_win_pct'], 0)
        self.assertEqual(row['repeat_by_4_pct'], 0)
        self.assertEqual(row['repeat_by_5_pct'], 100)
        self.assertFalse(any(r['sample'] for r in payload['active_repeat_rows'] if r['played'] == 5))
        rival = dict(rival='B', sequence='VDD', played=3, historical_played=23, historical_wins=10,
                     next_match='2026-09-03T12:00:00+00:00')
        data = {'six_match_stats': payload, 'leagues': {'GT': {'groups': [
            {'recent_h2h': {'players': [{'player': 'A', 'rivals': [rival]}]}}
        ]}}}
        html = render_active_repeat_matches(data)
        self.assertIn('<td>A</td>', html)
        self.assertIn('100.00%', html)
        data['h2h_exclusions'] = [('GT', 'a', 'b')]
        self.assertNotIn('<td>A</td>', render_active_repeat_matches(data))

    def test_active_pairs_require_one_win_in_first_two_and_incomplete_series(self):
        for sequence, included in [('V', False), ('VD', True), ('DV', True), ('VDDD', True), ('EVDDD', True),
                                   ('VV', False), ('DDV', False), ('VDDDDD', False), ('DD', False)]:
            rival = dict(rival='B', sequence=sequence, historical_played=30+len(sequence), historical_wins=15+sequence.count('V'))
            data = {'leagues': {'GT': {'groups': [{'recent_h2h': {'players': [{'player': 'A', 'rivals': [rival]}]}}]}}}
            self.assertEqual('<td>A</td>' in render_active_repeat_matches(data), included, sequence)

    def stats(self, sequence, wins=9):
        records = test_six_match_stats.SixMatchTests().history(wins=wins, sequence=sequence)
        return calculate_six_match_stats(records + records, datetime(2026, 9, 3, tzinfo=timezone.utc))

    def row(self, payload, condition=0):
        return [r for r in payload['repeat_rows'] if r['sample'] and r['condition'] ==
                ('Victoria en el primer partido', 'Victoria en el segundo partido',
                 'Primera victoria en el segundo partido')[condition]][0]

    def test_initial_win_is_not_itself_a_repeat(self):
        row = self.row(self.stats('VDDDDD'))
        self.assertEqual(row['sample'], 1)
        self.assertEqual(row['repeat_by_6_pct'], 0)
        self.assertEqual(row['next_win_pct'], 0)

    def test_immediate_and_later_repetition_are_distinct(self):
        row = self.row(self.stats('VDDDVD'))
        self.assertEqual(row['next_win_pct'], 0)
        self.assertEqual(row['repeat_by_4_pct'], 0)
        self.assertEqual(row['repeat_by_5_pct'], 100)
        self.assertEqual(row['repeat_by_6_pct'], 100)

    def test_second_win_and_first_win_on_second(self):
        payload = self.stats('VVDDDD')
        self.assertEqual(self.row(payload)['next_win_pct'], 100)
        self.assertEqual(self.row(payload, 1)['repeat_by_6_pct'], 0)
        self.assertFalse(any(r['sample'] for r in payload['repeat_rows'] if r['condition'].startswith('Primera')))
        payload = self.stats('DVDDDV')
        self.assertEqual(self.row(payload, 2)['repeat_by_5_pct'], 0)
        self.assertEqual(self.row(payload, 2)['repeat_by_6_pct'], 100)

    def test_boundaries_use_pre_series_history_not_future_wins(self):
        for wins, label in [(6, '30–<35%'), (7, '35–40% (incluidos)'), (8, '35–40% (incluidos)'), (9, '>40%')]:
            row = self.row(self.stats('VVVVVV', wins))
            self.assertEqual(row['band'], label)
            self.assertEqual(row['sample'], 1)
        self.assertTrue(all(r['sample'] == 0 for r in self.stats('VVVVVV', 5)['repeat_rows']))
        self.assertIn('Sin muestra', render_repeat_win_stats(self.stats('VDDDDD')))


if __name__ == '__main__':
    unittest.main()
