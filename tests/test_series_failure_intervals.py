from datetime import datetime, timezone
import unittest

from six_match_stats import failure_series_metrics, calculate_six_match_stats
from web_tracker.historical_pair_series import enrich_pair_stats
from tests import test_six_match_stats
from tests import test_underdog_matchups
from web_tracker.generate_site import render_underdog_matchups


class FailureIntervalTests(unittest.TestCase):
    def test_never_or_once_has_no_interval_mean(self):
        for failures, since in [([], None), ([False]*8, None), ([False, True, False, False], 2),
                                 ([False, True], 0)]:
            result = failure_series_metrics(failures)
            self.assertEqual(result['series_since_failure'], since)
            self.assertIsNone(result['failure_interval_mean'])
            self.assertEqual(result['failure_interval_count'], 0)

    def test_mean_uses_only_observed_complete_intervals(self):
        result = failure_series_metrics([False, True, False, True, True, False, False])
        self.assertEqual(result['series_since_failure'], 2)
        self.assertEqual(result['failure_interval_mean'], 1.5)  # Distances 2 and 1.
        self.assertEqual(result['failure_interval_count'], 2)

    def test_detailed_pair_last_failure(self):
        rows = test_six_match_stats.SixMatchTests().history(sequence='DDDDDD')
        stats = calculate_six_match_stats(rows, datetime(2026, 9, 3, tzinfo=timezone.utc),
                                          pair=('GT', 'david', 'fox'))
        self.assertEqual(stats['series_since_failure'], 0)
        self.assertIsNone(stats['failure_interval_mean'])

    def test_daily_sequences_and_totals_sorted_by_date_exclude_incomplete(self):
        daily = {'2026-09-08': 'VDDDDD', '2026-09-01': 'DDDDDD', '2026-09-07': 'DDDDDD',
                 '2026-09-03': {'W': 0, 'D': 3, 'L': 3}, '2026-09-02': 'VDDDDD',
                 '2026-09-05': 'DDDD', '2026-09-09': 'VDDDDD'}
        stats = enrich_pair_stats({}, [], datetime(2026, 9, 10, tzinfo=timezone.utc),
                                   ('GT', 'david', 'fox'), daily)
        # Complete series outcomes: fail, win, fail, fail, win, win.
        self.assertEqual(stats['complete_series'], 6)
        self.assertEqual(stats['zero_win_series'], 3)
        self.assertEqual(stats['series_since_failure'], 2)
        self.assertEqual(stats['failure_interval_mean'], 1.5)

    def test_table_shows_intervals_and_never_observed(self):
        data, rival = test_underdog_matchups.UnderdogMatchupTests().data()
        rival['pair_stats'] = dict(complete_series=10, zero_win_series=2,
                                   series_since_failure=3, failure_interval_mean=4.5)
        html = render_underdog_matchups(data)
        self.assertIn('Media entre sin V', html)
        self.assertIn('<td class="num">3</td><td class="num">4.50</td>', html)
        rival['pair_stats'] = dict(complete_series=10, zero_win_series=0)
        self.assertIn('Nunca en 10 series', render_underdog_matchups(data))
