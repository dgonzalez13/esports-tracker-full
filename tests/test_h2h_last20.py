import unittest
from datetime import datetime, timedelta, timezone

from tests import test_six_match_stats
from six_match_stats import calculate_six_match_stats
from web_tracker.generate_site import (build_last20_lookup, last20_cells, render_active_repeat_matches,
                                       render_six_match_stats)


class Last20Tests(unittest.TestCase):
    def test_first_horizons_group_jointly_by_prior_win_percentage_and_gap(self):
        reference = datetime(2026, 9, 3, tzinfo=timezone.utc)
        for wins, draw, thresholds in [(10, False, []), (10, True, [0]),
                                        (11, False, [0, 5]), (12, False, [0, 5, 10])]:
            records = test_six_match_stats.SixMatchTests().history(wins=wins, sequence='DDDDVD')
            if draw:
                records[19]['result'] = 'E'
            stats = calculate_six_match_stats(records + records, reference)
            for threshold in (35, 40):
                rows = [r for r in stats['win_gap_horizons'] if r['threshold'] == threshold and r['sample']]
                self.assertEqual(sorted({r['gap_threshold'] for r in rows}), thresholds)
                for gap in thresholds:
                    group = [r for r in rows if r['gap_threshold'] == gap]
                    self.assertEqual([r['sample'] for r in group], [1, 1, 1])
                    self.assertEqual([r['win_pct'] for r in group], [0, 100, 100])
            html = render_six_match_stats(stats)
            self.assertIn('<th>Dif.</th>', html)
            self.assertNotIn('Resultado condicionado a los primeros partidos sin ganar', html)
            self.assertEqual(html.count('<table>'), 1)

    def test_last20_chronological_deduplicated_final_results_only(self):
        reference = datetime(2026, 9, 3, tzinfo=timezone.utc)
        records = test_six_match_stats.SixMatchTests().history(wins=9, sequence='VDDDVD')
        expected = sorted(records, key=lambda row: row['timestamp_utc'])[-20:]
        future = dict(records[-1], match_id='future', result='V',
                      timestamp_utc=(reference + timedelta(days=1)).isoformat())
        pending = dict(records[-1], match_id='pending', result=None)
        lookup = build_last20_lookup(list(reversed(records)) + records + [future, pending], reference)
        row = lookup[('GT', 'david', 'fox')]
        self.assertEqual(row['available'], 20)
        self.assertEqual(row['win_pct'], sum(r['result'] == 'V' for r in expected) * 5)
        self.assertEqual(row['gap'], (sum(r['result'] == 'V' for r in expected)
                                     - sum(r['result'] == 'D' for r in expected)) * 5)

    def test_prior_window_does_not_include_current_series_and_requires_twenty(self):
        records = test_six_match_stats.SixMatchTests().history(wins=12, sequence='VVVVVV')
        start = datetime(2026, 9, 2, tzinfo=timezone.utc)
        prior = build_last20_lookup(records, start, exclusive=True)[('GT', 'david', 'fox')]
        self.assertEqual(last20_cells(prior), ['60.00%', '+20.00'])
        incomplete = build_last20_lookup(records[:19], start)[('GT', 'david', 'fox')]
        self.assertEqual(last20_cells(incomplete), ['—', '—'])

    def test_joint_groups_use_strict_prior_gap_and_current_prefix(self):
        reference = datetime(2026, 9, 3, tzinfo=timezone.utc)
        for wins, thresholds in [(10, []), (11, [0, 5]), (12, [0, 5, 10])]:
            stats = calculate_six_match_stats(test_six_match_stats.SixMatchTests().history(wins=wins, sequence='VDDDVD'), reference)
            rows = [r for r in stats['active_repeat_gap_rows'] if r['played'] == 3]
            self.assertEqual([r['gap_threshold'] for r in rows], thresholds)
            for row in rows:
                self.assertEqual(row['sample'], 1)
                self.assertEqual(row['next_win_pct'], 0)
                self.assertEqual(row['repeat_by_5_pct'], 100)
            self.assertFalse(any(r['played'] == 5 for r in stats['active_repeat_gap_rows']))
        rival = dict(rival='B', sequence='VDD', historical_played=23,
                     historical_wins=13, historical_losses=10,
                     prior20={'available': 20, 'win_pct': 60, 'gap': 20})
        html = render_active_repeat_matches({'six_match_stats': stats, 'leagues': {'GT': {'groups': [
            {'recent_h2h': {'players': [{'player': 'A', 'rivals': [rival]}]}}]}}})
        self.assertIn('V%20', html)
        self.assertIn('Dif.20', html)
        self.assertIn('data-alternative="100.00%"', html)
        self.assertIn('data-repeat-grouping', html)
