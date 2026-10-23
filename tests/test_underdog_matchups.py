from datetime import datetime, timedelta, timezone
import unittest

from six_match_stats import calculate_six_match_stats
from tests.test_h2h_analysis import perspective
from tests import test_six_match_stats
from web_tracker.generate_site import attach_recent_group_h2h, render_underdog_matchups
from web_tracker.pair_series_schedule import pair_series_schedule


class UnderdogMatchupTests(unittest.TestCase):
    reference = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)

    def data(self, wins=31, losses=50, sequence='', stats=None):
        rival = dict(rival='Fox', historical_played=100, historical_wins=wins,
                     historical_losses=losses, current_pair_sequence=sequence,
                     pair_stats=stats or {'complete_series': 8, 'zero_win_series': 2})
        return {'leagues': {'GT': {'groups': [{'recent_h2h': {'players': [
            {'player': 'David', 'rivals': [rival]}]}}]}}}, rival

    def fixture(self, index, minute=0, **overrides):
        row = perspective(index, None, timestamp=(self.reference + timedelta(minutes=minute)).isoformat())
        row['fixture_status'] = 'scheduled'
        row.update(overrides)
        return row

    def test_strict_thresholds_and_first_win_removes_pair(self):
        for wins, losses, sequence, shown in [(30, 50, '', False), (31, 31, '', False),
                                             (31, 50, 'DED', True), (31, 50, 'DEV', False)]:
            data, _ = self.data(wins, losses, sequence)
            self.assertEqual('<td>David</td>' in render_underdog_matchups(data), shown)

    def test_individual_failure_count_and_no_sample(self):
        data, rival = self.data()
        html = render_underdog_matchups(data)
        self.assertIn('31.00%', html)
        self.assertIn('50.00%', html)
        self.assertIn('<td class="num">2</td><td class="num">8</td><td class="num">25.00%</td>', html)
        rival['pair_stats'] = {'complete_series': 0, 'zero_win_series': 0}
        self.assertIn('<td class="num">—</td><td class="num">0</td><td class="num">—</td>', render_underdog_matchups(data))

    def test_all_six_hours_then_only_remaining_hours(self):
        data, rival = self.data()
        rival['pair_fixtures'] = [{'timestamp': (self.reference + timedelta(minutes=i*15)).isoformat(),
                                  'started': False} for i in range(1, 8)]
        html = render_underdog_matchups(data)
        for time in ('12:15', '12:30', '12:45', '13:00', '13:15', '13:30'):
            self.assertIn(time, html)
        self.assertNotIn('13:45', html)
        rival['current_pair_sequence'] = 'DD'
        html = render_underdog_matchups(data)
        self.assertIn('13:00', html)
        self.assertNotIn('13:15', html)

    def test_mirrored_calendar_and_finished_results_are_not_pending(self):
        future = self.fixture(1, minute=15)
        mirror = dict(future, player='Fox', player_key='fox', rival='David', rival_key='david')
        past = self.fixture(2, minute=-10)
        history = [dict(past, result='D', match_id='different-source-id')]
        schedule = {'sources': {'GT': {'records': [future, mirror, past]}}}
        sequences, fixtures = pair_series_schedule(history + history, schedule, self.reference)
        self.assertEqual(sequences[('GT', 'david', 'fox')], 'D')
        self.assertEqual(sequences[('GT', 'fox', 'david')], 'V')
        self.assertEqual(len(fixtures[('GT', ('david', 'fox'))]), 1)

    def test_calendar_final_win_hides_pair_before_history_collection(self):
        group = {'target': ['David', 'Fox'], 'h2h_matrix': [
            {'player': 'David', 'rivals': [{'rival': 'Fox', 'matches': 100, 'W': 31, 'L': 50,
                                           'win_pct': 31}]}]}
        data = {'leagues': {'GT': {'groups': [group]}}}
        final = self.fixture(1, minute=-5, result='V', fixture_status='finished')
        attach_recent_group_h2h(data, [], self.reference, {'sources': {'GT': {'records': [final]}}})
        self.assertNotIn('<td>David</td>', render_underdog_matchups(data))

    def test_unknown_started_fixture_is_kept_and_missing_hours_are_explicit(self):
        pending = self.fixture(1, minute=-5)
        _, fixtures = pair_series_schedule([], {'sources': {'GT': {'records': [pending]}}}, self.reference)
        data, rival = self.data()
        rival['pair_fixtures'] = fixtures[('GT', ('david', 'fox'))]
        html = render_underdog_matchups(data)
        self.assertIn('sin resultado', html)
        self.assertIn('Faltan 5 horarios por publicar', html)

    def test_exclusions_and_duplicate_groups(self):
        data, _ = self.data()
        data['leagues']['GT']['groups'] *= 2
        self.assertEqual(render_underdog_matchups(data).count('<td>David</td>'), 1)
        data['excluded_player_keys'] = [('GT', 'fox')]
        self.assertNotIn('<td>David</td>', render_underdog_matchups(data))
        data.pop('excluded_player_keys')
        data['h2h_exclusions'] = [('GT', 'david', 'fox')]
        self.assertNotIn('<td>David</td>', render_underdog_matchups(data))

    def test_six_match_failures_require_six_closed_observed_results(self):
        ref = datetime(2026, 9, 3, tzinfo=timezone.utc)
        for sequence, total, failures in [('DDDDDD', 1, 1), ('DDDDDE', 1, 1),
                                          ('DDDDDV', 1, 0), ('DDDDD', 0, 0), ('VDD', 0, 0)]:
            records = test_six_match_stats.SixMatchTests().history(sequence=sequence)
            stats = calculate_six_match_stats(records + records, ref, pair=('GT', 'david', 'fox'))
            self.assertEqual((stats['complete_series'], stats['zero_win_series']), (total, failures))
            other = calculate_six_match_stats(records, ref, pair=('GT', 'david', 'other'))
            self.assertEqual(other['zero_win_series'], 0)


if __name__ == '__main__':
    unittest.main()
