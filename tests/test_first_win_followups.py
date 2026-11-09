from datetime import datetime, timezone
import unittest

from six_match_stats import first_win_followups, calculate_six_match_stats
from web_tracker.historical_pair_series import enrich_pair_stats
from web_tracker.generate_site import render_first_win_followups
from tests import test_six_match_stats


class FirstWinFollowupTests(unittest.TestCase):
    def windows(self, rows, position=1):
        return [r for r in rows if r['first_win_position'] == position and r['window'] != 0]

    def test_initial_win_is_excluded_and_windows_start_after_it(self):
        rows = self.windows(first_win_followups([('GT', 'VDDDDV')]))
        self.assertEqual([r['sample'] for r in rows], [1, 1, 1])
        self.assertEqual([r['win_pct'] for r in rows], [0, 0, 100])

    def test_first_win_position_controls_eligible_windows(self):
        for sequence, position, expected in [('VDDDDV', 1, [0, 0, 100]),
                ('DVDDDV', 2, [0, 100, None]), ('DDVDDV', 3, [100, None, None]),
                ('DDDVVD', 4, [None]*3), ('DDDDVV', 5, [None]*3), ('DDDDDV', 6, [None]*3)]:
            rows = self.windows(first_win_followups([('GT', sequence)]), position)
            self.assertEqual([r['win_pct'] for r in rows], expected, sequence)
            self.assertEqual([r['first_win_series'] for r in rows], [1]*3)

    def test_late_first_win_remaining_games_are_separate(self):
        rows = first_win_followups([('GT', 'DDDVVD'), ('GT', 'DDDVDD'),
                                   ('GT', 'DDDDVV'), ('GT', 'DDDDVD'), ('GT', 'DDDDDV')])
        for position in (4, 5):
            row = next(r for r in rows if r['first_win_position'] == position and r['window'] == 0)
            self.assertEqual(row['sample'], 2)
            self.assertEqual(row['win_pct'], 50)
        last = next(r for r in rows if r['first_win_position'] == 6 and r['window'] == 0)
        self.assertEqual(last['sample'], 0)
        self.assertIsNone(last['win_pct'])

    def test_missing_future_does_not_become_failure(self):
        rows = self.windows(first_win_followups([('GT', 'VDV'), ('GT', 'VDDD'), ('GT', 'V')]))
        self.assertEqual([r['sample'] for r in rows], [2, 1, 1])
        self.assertEqual([r['win_pct'] for r in rows], [50, 100, 100])

    def test_archive_used_once_and_unordered_totals_excluded(self):
        records = test_six_match_stats.SixMatchTests().history(sequence='VDDDDV')[-6:]
        reference = datetime(2026, 9, 4, tzinfo=timezone.utc)
        stats = calculate_six_match_stats(records, reference, pair=('GT', 'david', 'fox'))
        result = enrich_pair_stats(stats, records, reference, ('GT', 'david', 'fox'),
            {'2026-09-02': 'VDDDDV', '2026-09-01': 'VDVDDD', '2026-08-31': {'W': 3, 'D': 0, 'L': 3}})
        self.assertEqual([r['sample'] for r in self.windows(result['first_win_followups'])], [2, 2, 2])
        self.assertEqual([r['win_pct'] for r in self.windows(result['first_win_followups'])], [50, 50, 100])

    def test_long_detailed_series_never_uses_victory_after_sixth(self):
        records = test_six_match_stats.SixMatchTests().history(sequence='DDDVDDDDV')[-9:]
        result = calculate_six_match_stats(records, datetime(2026, 9, 4, tzinfo=timezone.utc),
                                            pair=('GT', 'david', 'fox'))
        row = next(r for r in result['first_win_followups'] if r['first_win_position'] == 4 and r['window'] == 0)
        self.assertEqual(row['win_pct'], 0)
        self.assertEqual(row['sample'], 1)

    def test_table_includes_all_current_pairs_independent_of_current_win_count(self):
        rivals = [dict(rival=f'B{i}', sequence=sequence, historical_played=3,
                       historical_wins=0, historical_losses=3, historical_win_pct=0,
                       pair_stats={'first_win_followups': first_win_followups([('GT', 'VDVDDD')])})
                  for i, sequence in enumerate(('', 'DDD', 'VV', 'DDV'))]
        data = {'bettable_keys': [], 'leagues': {'GT': {'groups': [
            {'recent_h2h': {'players': [{'player': 'A', 'rivals': rivals}]}}]*2}}}
        html = render_first_win_followups(data)
        self.assertEqual(html.count('<td>A</td>'), 4)
        self.assertIn('Otra V en +3', html)
        data['h2h_exclusions'] = [('GT', 'a', 'b0')]
        self.assertNotIn('<td>B0</td>', render_first_win_followups(data))
        self.assertEqual(html.count('100.00% (n=1)'), 3)
