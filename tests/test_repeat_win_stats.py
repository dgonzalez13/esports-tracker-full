import unittest
from datetime import datetime, timezone
from tests import test_six_match_stats
from six_match_stats import calculate_six_match_stats
from web_tracker.generate_site import render_repeat_win_stats


class RepeatWinTests(unittest.TestCase):
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
