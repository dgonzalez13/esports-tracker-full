from datetime import datetime, timezone
import unittest

from six_match_stats import pair_repeat_statistics, calculate_six_match_stats
from tests import test_six_match_stats
from web_tracker.historical_pair_series import enrich_pair_stats


class ExpandedRepeatTests(unittest.TestCase):
    def row(self, rows, played=2, position=1):
        return next(r for r in rows if r['played'] == played and r['win_position'] == position)

    def test_requires_new_win_and_uses_separate_horizon_denominators(self):
        rows = pair_repeat_statistics([('GT', 'VDDD'), ('GT', 'VDV')])
        row = self.row(rows)
        self.assertEqual(row['sample'], 2)
        self.assertEqual(row['next_win_pct'], 50)
        self.assertEqual(row['repeat_by_4_pct'], 50)
        self.assertEqual(row['repeat_by_5_sample'], 1)
        self.assertEqual(row['repeat_by_5_pct'], 100)
        self.assertEqual(row['repeat_by_6_sample'], 1)
        self.assertEqual(row['repeat_by_6_pct'], 100)

    def test_ignores_priors_and_preserves_current_prefix_condition(self):
        records = test_six_match_stats.SixMatchTests().history(wins=0, sequence='VDVDDD')
        stats = calculate_six_match_stats(records, datetime(2026, 9, 3, tzinfo=timezone.utc),
                                          pair=('GT', 'david', 'fox'))
        self.assertEqual(self.row(stats['pair_repeat_rows'])['sample'], 1)
        self.assertFalse(any(r['sample'] for r in stats['active_repeat_rows']))
        self.assertFalse(any(r['played'] >= 3 for r in stats['pair_repeat_rows']))

    def test_second_initial_win_position_is_separate(self):
        rows = pair_repeat_statistics([('GT', 'DVDDVD'), ('GT', 'VDVDDD')])
        row = self.row(rows, position=2)
        self.assertEqual(row['sample'], 1)
        self.assertEqual(row['next_win_pct'], 0)
        self.assertEqual(row['repeat_by_4_pct'], 0)
        self.assertEqual(row['repeat_by_5_pct'], 100)

    def test_archive_adds_ordered_series_once_and_skips_totals(self):
        records = test_six_match_stats.SixMatchTests().history(sequence='VDVDDD')[-6:]
        stats = calculate_six_match_stats(records, datetime(2026, 9, 4, tzinfo=timezone.utc),
                                          pair=('GT', 'david', 'fox'))
        stats = enrich_pair_stats(stats, records, datetime(2026, 9, 4, tzinfo=timezone.utc),
            ('GT', 'david', 'fox'), {'2026-09-02': 'VDVDDD', '2026-09-01': 'VDDDDV',
                                    '2026-08-31': {'W': 2, 'D': 0, 'L': 4}})
        row = self.row(stats['pair_repeat_rows'])
        self.assertEqual(row['sample'], 2)
        self.assertEqual(row['next_win_pct'], 50)
        self.assertEqual(row['repeat_by_6_pct'], 100)
