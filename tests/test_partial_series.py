import unittest
from datetime import datetime, timedelta, timezone

from six_match_stats import calculate_six_match_stats
from tests import test_six_match_stats
from web_tracker.generate_site import pair_repeat_cell
from recover_saved_history import recover


class PartialSeriesTests(unittest.TestCase):
    reference = datetime(2026, 9, 3, tzinfo=timezone.utc)

    def history(self, sequence):
        return test_six_match_stats.SixMatchTests().history(sequence=sequence)

    def test_each_conditional_horizon_requires_enough_results(self):
        for sequence, samples in [('DDDV', [1, 0, 0]), ('DDDDV', [1, 1, 0]),
                                  ('DDDDDV', [1, 1, 1])]:
            payload = calculate_six_match_stats(self.history(sequence), self.reference)
            for k in (0, 1, 2, 3):
                rows = [r for r in payload['conditional_horizons']
                        if r['threshold'] == 40 and r['initial_without_win'] == k
                        and r['band'].startswith('A por')]
                self.assertEqual([r['sample'] for r in rows], samples)
                expected = [((100 if 'V' in sequence[k:h] else 0)
                             if samples[i] else None) for i, h in enumerate((4, 5, 6))]
                self.assertEqual([r['win_pct'] for r in rows], expected)

    def test_partial_session_without_win_is_not_a_six_match_failure(self):
        payload = calculate_six_match_stats(self.history('DDDD'), self.reference)
        rows = [r for r in payload['conditional_horizons']
                if r['threshold'] == 40 and r['initial_without_win'] == 0 and r['sample']]
        self.assertEqual([(r['horizon'], r['win_pct']) for r in rows], [(4, 0)])
        self.assertFalse(any(r['sample'] for r in payload['rows']))

    def test_repeat_denominators_and_cells_are_specific_to_each_horizon(self):
        payload = calculate_six_match_stats(self.history('VDDV'), self.reference)
        row = next(r for r in payload['active_repeat_rows']
                   if r['band'] == '>40%' and r['played'] == 2 and r['win_position'] == 1)
        self.assertEqual(row['repeat_by_4_sample'], 1)
        self.assertEqual(row['repeat_by_5_sample'], 0)
        self.assertEqual(pair_repeat_cell(row, 'repeat_by_4_pct'), '100.00% (n=1)')
        self.assertEqual(pair_repeat_cell(row, 'repeat_by_5_pct'), '\u2014')

    def test_mixed_lengths_use_independent_denominators(self):
        for first, second, key in [('DDDV', 'DDDDDV', 'conditional_horizons'),
                                   ('VDDV', 'VDDDDV', 'active_repeat_rows')]:
            later = self.history(second)[20:]
            for row in later:
                stamp = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00'))
                row['timestamp_utc'] = (stamp + timedelta(days=1)).isoformat()
                row['match_id'] = 'later-' + row['match_id']
            payload = calculate_six_match_stats(self.history(first) + later,
                                                self.reference + timedelta(days=1))
            if key == 'conditional_horizons':
                rows = [r for r in payload[key] if r['threshold'] == 40
                        and r['initial_without_win'] == 0 and r['band'].startswith('A por')]
                self.assertEqual([(r['sample'], r['win_pct']) for r in rows],
                                 [(2, 50), (1, 0), (1, 100)])
            else:
                row = next(r for r in payload[key] if r['band'] == '>40%'
                           and r['played'] == 2 and r['win_position'] == 1)
                self.assertEqual([pair_repeat_cell(row, f'repeat_by_{h}_pct') for h in (4, 5, 6)],
                                 ['50.00% (n=2)', '0.00% (n=1)', '100.00% (n=1)'])

    def test_open_or_overlong_sessions_are_not_used(self):
        for sequence, reference in [('DDDD', datetime(2026, 9, 2, 0, 20, tzinfo=timezone.utc)),
                                     ('DDDDDDV', self.reference)]:
            payload = calculate_six_match_stats(self.history(sequence), reference)
            self.assertFalse(any(r['sample'] for r in payload['conditional_horizons']))

    def test_recovery_deduplicates_and_preserves_existing_and_conflicting_matches(self):
        row = dict(self.history('DDDD')[0], home_score=1, away_score=0, home_away='home')
        merged, summary = recover([], [[row], [row]])
        self.assertEqual(merged, [row])
        self.assertEqual(summary['added_perspectives'], 1)
        merged, summary = recover([row], [[dict(row, result='D')]])
        self.assertEqual(merged, [row])
        self.assertEqual(summary['conflicting_matches_skipped'], 1)
        merged, summary = recover([], [[row], [dict(row, result='D')]])
        self.assertEqual(merged, [])


if __name__ == '__main__':
    unittest.main()
