import unittest

from web_tracker.bet_candidates import first_win_window_candidate
from web_tracker.generate_site import render_first_win_window_candidates


class WindowCandidateTests(unittest.TestCase):
    def rival(self, sequence='V', probabilities=None):
        first = sequence.index('V')+1 if 'V' in sequence else 1
        probabilities = probabilities or {1: 0, 3: 0, 4: 0, 5: 95, 0: 0}
        return dict(rival='B', current_pair_sequence=sequence,
                    pair_stats={'first_win_followups': [dict(league='GT', first_win_position=first,
                        window=window, sample=20, win_pct=pct) for window, pct in probabilities.items()]},
                    pair_fixtures=[dict(timestamp=f'2026-11-09T{hour}:00:00+00:00', started=False)
                                   for hour in range(10, 15)])

    def test_tail_aligned_stakes_for_one_to_five_remaining(self):
        for played in range(1, 6):
            rival = self.rival('V'+'D'*(played-1))
            line = first_win_window_candidate(rival, 'GT')[1]
            self.assertTrue(line.startswith(f'[{played+1}] {5*2**(played-1)} '))
            self.assertEqual(line.count(' --- '), 5-played)
            self.assertIn('Hasta partido 6: 95.00% (n=20)', line)

    def test_first_qualifying_horizon_not_highest_percentage(self):
        rival = self.rival('DV', {1: 20, 3: 91, 4: 100})
        line = first_win_window_candidate(rival, 'GT')[1]
        self.assertTrue(line.startswith('[3] 20 '))
        self.assertIn('Hasta partido 5: 91.00%', line)

    def test_consecutive_win_can_be_first_horizon_and_expired_ones_are_skipped(self):
        rival = self.rival('V', {1: 95, 3: 99, 5: 100})
        self.assertTrue(first_win_window_candidate(rival, 'GT')[1].startswith('[2] 80 '))
        rival['current_pair_sequence'] = 'VDD'
        line = first_win_window_candidate(rival, 'GT')[1]
        self.assertTrue(line.startswith('[4] 80 '))
        self.assertIn('Hasta partido 4: 99.00%', line)

    def test_strict_threshold_samples_and_single_victory(self):
        for sequence in ('DDD', 'VV', 'VDDDDD'):
            self.assertIsNone(first_win_window_candidate(self.rival(sequence), 'GT'))
        rival = self.rival('V', {5: 90})
        self.assertIsNone(first_win_window_candidate(rival, 'GT'))
        rival['pair_stats']['first_win_followups'][0].update(win_pct=95, sample=0)
        self.assertIsNone(first_win_window_candidate(rival, 'GT'))

    def test_late_first_win_and_cancellations(self):
        rival = self.rival('DDDV', {0: 95})
        self.assertTrue(first_win_window_candidate(rival, 'GT')[1].startswith('[5] 40 '))
        rival['pair_cancelled'] = 1
        self.assertIsNone(first_win_window_candidate(rival, 'GT'))
        rival = self.rival('V', {5: 100})
        rival['pair_cancelled'] = 1
        self.assertIsNone(first_win_window_candidate(rival, 'GT'))

    def test_no_fabricated_hours_and_duplicate_excluded_rows(self):
        rival = self.rival()
        rival['pair_fixtures'] = rival['pair_fixtures'][:2]
        self.assertIn('Faltan 3', first_win_window_candidate(rival, 'GT')[1])
        data = {'leagues': {'GT': {'groups': [{'recent_h2h': {'players': [
            {'player': 'A', 'rivals': [rival]}]}}]*2}}}
        html = render_first_win_window_candidates(data)
        self.assertEqual(html.count('GT A - B [2] 5'), 1)
        data['h2h_exclusions'] = [('GT', 'a', 'b')]
        self.assertNotIn('GT A - B', render_first_win_window_candidates(data))
