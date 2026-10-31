from datetime import datetime, timezone
import unittest

from web_tracker.bet_candidates import candidate, six_rating
from web_tracker.generate_site import render_bet_candidates
from tests.test_underdog_matchups import UnderdogMatchupTests
from tests.test_six_match_stats import SixMatchTests
from six_match_stats import calculate_six_match_stats


class CandidateTests(unittest.TestCase):
    def rival(self):
        return dict(historical_played=100, historical_wins=50, historical_losses=20,
                    historical_win_pct=50, wins=0, sequence='', current_pair_sequence='',
                    last20={'available': 20, 'gap': 30},
                    pair_stats={'complete_series': 20, 'zero_win_series': 0},
                    pair_fixtures=[{'timestamp': f'2026-10-31T{10+i:02}:00:00+00:00', 'started': False}
                                   for i in range(6)])

    def test_number_and_stake_for_both_progressions(self):
        for horizon, initial in [(4, 10), (6, 3)]:
            for played in range(horizon):
                rival = self.rival()
                rival['current_pair_sequence'] = 'D' * played
                line = candidate(rival, horizon)[1]
                self.assertTrue(line.startswith(f'[{played+1}] {initial * 2**played} 31/10 11:00'))
                self.assertEqual(line.count(' --- '), horizon-played-1)

    def test_strict_filters_results_missing_data_and_horizon(self):
        for updates in [dict(historical_wins=37), dict(historical_losses=50),
                        dict(last20={'available': 20, 'gap': 0}), dict(last20={'available': 19, 'gap': 30}),
                        dict(current_pair_sequence='DV'), dict(current_pair_sequence='DDDD'),
                        dict(pair_fixtures=[])]:
            rival = self.rival()
            rival.update(updates)
            self.assertIsNone(candidate(rival, 4), updates)
        rival = self.rival()
        rival['pair_fixtures'][0]['started'] = True
        self.assertIsNone(candidate(rival, 4))

    def test_missing_hours_not_invented(self):
        rival = self.rival()
        rival['pair_fixtures'] = rival['pair_fixtures'][:1]
        self.assertIn('Faltan 5 horarios', candidate(rival, 6)[1])

    def test_six_levels_and_independent_filters(self):
        for wins, losses, level in [(31, 20, 1), (31, 31, 2), (31, 36, 2),
                                     (31, 37, 3), (31, 41, 3), (31, 42, None), (30, 31, None)]:
            rival = self.rival()
            rival.update(historical_wins=wins, historical_losses=losses, last20={})
            rating = six_rating(rival)
            self.assertEqual(rating[0] if rating else None, level)
            self.assertEqual(candidate(rival, 6) is not None, level is not None)
            self.assertIsNone(candidate(rival, 4))

    def test_six_sample_and_failure_boundaries(self):
        for sample, failures, accepted, warnings in [(7, 0, False, 0), (8, 0, True, 1),
                (9, 0, True, 1), (10, 0, True, 0), (20, 1, True, 1),
                (10, 1, True, 1), (9, 1, False, 0), (8, 1, False, 0), (100, 11, False, 0)]:
            rival = self.rival()
            rival['pair_stats'] = {'complete_series': sample, 'zero_win_series': failures}
            rating = six_rating(rival)
            self.assertEqual(rating is not None, accepted, (sample, failures))
            if rating:
                self.assertEqual(len(rating[1]), warnings)

    def test_six_color_label_and_warning_rendered(self):
        data, rival = UnderdogMatchupTests().data()
        rival.update(self.rival())
        rival.update(historical_wins=31, historical_losses=39, last20={},
                     pair_stats={'complete_series': 9, 'zero_win_series': 0})
        html = render_bet_candidates(data)
        self.assertIn('candidate-level-3', html)
        self.assertIn('Nivel 3', html)
        self.assertIn('Solo 9 series de 6', html)
        self.assertEqual(html.count('GT David - Fox'), 1)

    def test_source_exclusions_and_duplicate_groups(self):
        data, rival = UnderdogMatchupTests().data()
        rival.update(self.rival())
        data['leagues']['GT']['groups'] *= 2
        html = render_bet_candidates(data)
        self.assertEqual(html.count('GT David - Fox'), 2)  # Once per horizon.
        data['h2h_exclusions'] = [('GT', 'david', 'fox')]
        self.assertNotIn('GT David - Fox', render_bet_candidates(data))

    def test_long_sessions_contribute_first_six_without_sliding_samples(self):
        records = SixMatchTests().history(sequence='DDDDDVDD')[-8:]
        payload = calculate_six_match_stats(records, datetime(2026, 9, 3, tzinfo=timezone.utc),
                                            pair=('GT', 'david', 'fox'))
        rows = [r for r in payload['pair_horizons'] if r['initial_without_win'] == 0]
        self.assertEqual([r['sample'] for r in rows], [1, 1, 1])
        self.assertEqual([r['win_pct'] for r in rows], [0, 0, 100])
        self.assertEqual(payload['complete_series'], 0)


if __name__ == '__main__':
    unittest.main()
