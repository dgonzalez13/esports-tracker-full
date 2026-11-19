import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.test_h2h_analysis import perspective
from tests.test_bet_candidates import CandidateTests
from web_tracker.eadriatic_inference import infer_eadriatic_pairs
from web_tracker.generate_site import (attach_recent_group_h2h, render_bet_candidates,
                                        render_eadriatic_possible_pairs)


class InferenceTests(unittest.TestCase):
    reference = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)

    def record(self, index=1, minutes=-30, **overrides):
        row = perspective(index, 'D', league='EADRIATIC',
                          timestamp=(self.reference + timedelta(minutes=minutes)).isoformat())
        row['source_type'] = 'betsapi_saved_html'
        row.update(overrides)
        return row

    def test_deduplicates_and_never_fabricates_fixture_time(self):
        row = self.record()
        duplicate = dict(row, match_id='official:1', source_type='eadriatic_html')
        result = infer_eadriatic_pairs([row, row, duplicate], self.reference, {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['observed'], 1)
        self.assertEqual(result[0]['possible_remaining'], 5)
        self.assertNotIn('next_match', result[0])
        self.assertNotIn('timestamp', result[0])

    def test_stale_future_other_league_and_official_only_not_projected(self):
        for row in (self.record(minutes=-481), self.record(minutes=1),
                    self.record(league='GT'), self.record(source_type='eadriatic_html')):
            self.assertEqual(infer_eadriatic_pairs([row], self.reference, {}), [])

    def test_full_six_and_confirmed_calendar_not_projected(self):
        rows = [self.record(i, minutes=-120 + i*15) for i in range(6)]
        self.assertEqual(infer_eadriatic_pairs(rows, self.reference, {}), [])
        fixtures = {('EADRIATIC', ('david', 'fox')): [{'timestamp': self.reference.isoformat()}]}
        self.assertEqual(infer_eadriatic_pairs(rows[:2], self.reference, fixtures), [])

    def test_unknown_pair_can_qualify_without_changing_configured_groups(self):
        data = {'leagues': {'EADRIATIC': {'groups': []}}}
        stats = CandidateTests().rival()['pair_stats']
        with patch('web_tracker.generate_site.calculate_six_match_stats', return_value=stats):
            attach_recent_group_h2h(data, [self.record()], self.reference)
        self.assertEqual(data['leagues']['EADRIATIC']['groups'], [])
        self.assertEqual(len(data['inferred_eadriatic_players']), 2)
        candidate_html = render_bet_candidates(data)
        # With no historical sample, merely observing a pair cannot qualify it.
        self.assertNotIn('EADRIATIC David - Fox', candidate_html)
        row = data['inferred_eadriatic_players'][0]['rivals'][0]
        row.update(historical_played=100, historical_win_pct=50, historical_wins=50,
                   historical_losses=20, wins=0, last20={'available': 20, 'win_pct': 50})
        html = render_bet_candidates(data)
        self.assertIn('EADRIATIC David - Fox', html)
        self.assertIn('Registrados: 1; posibles pendientes hasta 6: 5', html)
        table = render_eadriatic_possible_pairs(data)
        self.assertIn('Indicar primera hora o importar mas resultados', table)
        data['h2h_exclusions'] = [('EADRIATIC', 'david', 'fox')]
        self.assertNotIn('EADRIATIC David - Fox', render_bet_candidates(data))
        self.assertNotIn('<td>David</td>', render_eadriatic_possible_pairs(data))

    def test_configured_pair_preserves_historical_totals_and_is_not_duplicated(self):
        group = {'target': ['David', 'Fox'], 'h2h_matrix': [
            {'player': 'David', 'rivals': [{'rival': 'Fox', 'matches': 300, 'W': 150,
                                         'L': 100, 'win_pct': 50}]}]}
        data = {'leagues': {'EADRIATIC': {'groups': [group]}}}
        attach_recent_group_h2h(data, [self.record()], self.reference)
        self.assertEqual(data['inferred_eadriatic_players'], [])
        row = group['recent_h2h']['players'][0]['rivals'][0]
        self.assertEqual(row['historical_played'], 300)
        self.assertEqual(row['inferred_pair']['observed'], 1)

    def test_excluded_players_and_expired_observations_do_not_linger(self):
        data = {'excluded_player_keys': [('EADRIATIC', 'david')]}
        attach_recent_group_h2h(data, [self.record()], self.reference)
        self.assertEqual(data['eadriatic_possible_pairs'], [])
        data = {}
        attach_recent_group_h2h(data, [self.record()], self.reference)
        self.assertEqual(len(data['eadriatic_possible_pairs']), 1)
        attach_recent_group_h2h(data, [self.record()], self.reference + timedelta(hours=9))
        self.assertEqual(data['eadriatic_possible_pairs'], [])
        self.assertEqual(data['inferred_eadriatic_players'], [])
