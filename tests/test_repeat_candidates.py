import unittest

from web_tracker.bet_candidates import repeat_candidate
from web_tracker.generate_site import render_repeat_candidates


class RepeatCandidateTests(unittest.TestCase):
    def rival(self, pct=45, pct20=45, pct6=95):
        return {'rival': 'Fox', 'sequence': 'VDD', 'historical_played': 103,
                'historical_wins': pct+1, 'prior20': {'available': 20, 'win_pct': pct20},
                'pair_stats': {'pair_repeat_rows': [dict(league='GT', win_position=1, played=3,
                                 sample=20, repeat_by_6_sample=20, repeat_by_6_pct=pct6)]},
                'pair_fixtures': [dict(timestamp=f'2026-11-06T{hour}:00:00+00:00', started=False)
                                  for hour in (10, 11, 12)]}

    def data(self, rival):
        return {'leagues': {'GT': {'groups': [{'recent_h2h': {'players': [
            {'player': 'David', 'rivals': [rival]}]}}]}}}

    def test_marks_and_percentage_boundaries(self):
        for pct, pct20, pct6, stars in [(45, 45, 95, ''), (38, 44, 95, '*'),
                (44, 38, 95, '*'), (38, 44, 85, '**'), (45, 45, 90, '*'),
                (40, 45, 91, ''), (45, 40, 91, ''), (40, 40, 95, None),
                (39, 41, 95, None), (45, 45, 84.99, None)]:
            result = repeat_candidate(self.rival(pct, pct20, pct6), 'GT')
            self.assertEqual(result[1] if result else None, stars, (pct, pct20, pct6))

    def test_number_stake_and_hours(self):
        result = repeat_candidate(self.rival(), 'GT')
        self.assertEqual(result[2], '[4] 20 11:00 --- 12:00 --- 13:00')

    def test_requires_at_least_three_and_single_initial_win(self):
        for sequence in ['VD', 'VDDDDD', 'VVD', 'DDV', 'DDD']:
            rival = self.rival()
            rival['sequence'] = sequence
            self.assertIsNone(repeat_candidate(rival, 'GT'))
        rival = self.rival()
        rival['sequence'] = 'DVD'
        rival['pair_stats']['pair_repeat_rows'][0]['win_position'] = 2
        self.assertIsNotNone(repeat_candidate(rival, 'GT'))

    def test_later_steps_use_current_sample_number_stake_and_remaining_hours(self):
        for played, stake in [(3, 20), (4, 40), (5, 80)]:
            rival = self.rival()
            rival['sequence'] = 'V' + 'D'*(played-1)
            rival['historical_played'] = 100+played
            rival['pair_stats']['pair_repeat_rows'][0]['played'] = played
            line = repeat_candidate(rival, 'GT')[2]
            self.assertTrue(line.startswith(f'[{played+1}] {stake} '))
            self.assertEqual(line.count(' --- '), 5-played)
            self.assertNotIn('cancelación', line)
        rival['pair_stats']['pair_repeat_rows'][0]['played'] = 3
        self.assertIsNone(repeat_candidate(rival, 'GT'))

    def test_no_guessing_missing_percentages_or_samples(self):
        for changes in [dict(prior20={}), dict(prior20={'available': 19, 'win_pct': 90}),
                        dict(pair_stats={}), dict(pair_fixtures=[])]:
            rival = self.rival()
            rival.update(changes)
            self.assertIsNone(repeat_candidate(rival, 'GT'))
        rival = self.rival()
        rival['pair_stats']['pair_repeat_rows'][0]['repeat_by_6_sample'] = 0
        self.assertIsNone(repeat_candidate(rival, 'GT'))

    def test_cancelled_and_missing_hours(self):
        rival = self.rival()
        rival['pair_cancelled'] = 1
        self.assertIn('Solo 2', repeat_candidate(rival, 'GT')[2])
        rival['pair_cancelled'] = 0
        rival['pair_fixtures'] = rival['pair_fixtures'][:1]
        self.assertIn('Faltan 2', repeat_candidate(rival, 'GT')[2])

    def test_exclusions_duplicates_and_leading_marks(self):
        data = self.data(self.rival(38, 44, 85))
        data['leagues']['GT']['groups'] *= 2
        html = render_repeat_candidates(data)
        self.assertEqual(html.count('**GT David - Fox [4] 20'), 1)
        data['h2h_exclusions'] = [('GT', 'david', 'fox')]
        self.assertNotIn('GT David - Fox', render_repeat_candidates(data))
        data.pop('h2h_exclusions')
        data['bettable_keys'] = [('GT', 'david')]
        self.assertNotIn('GT David - Fox', render_repeat_candidates(data))
