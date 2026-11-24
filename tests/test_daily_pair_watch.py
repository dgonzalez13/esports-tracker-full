import unittest
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from tests.test_h2h_analysis import perspective
from web_tracker.daily_pair_watch import daily_pair_sequences
from web_tracker.generate_site import render_daily_pair_watch, attach_recent_group_h2h, render_page


class DailyPairWatchTests(unittest.TestCase):
    reference = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)

    def data(self, sequence='', total=45, recent=40, available=20):
        row = dict(rival='Fox', historical_win_pct=total, historical_played=100,
                   last20={'available': available, 'win_pct': recent}, daily_pair_sequence=sequence)
        group = {'recent_h2h': {'players': [{'player': 'David', 'rivals': [row]}]}}
        return {'leagues': {'GT': {'groups': [group]}}, 'daily_pair_watch_date': '2026-11-24'}

    def test_strict_thresholds_and_complete_last_twenty(self):
        for total, recent, available, included in [(35, 40, 20, False), (40, 35, 20, False),
                (35.01, 35.01, 20, True), (45, 40, 19, False), (None, 40, 20, False)]:
            html = render_daily_pair_watch(self.data(total=total, recent=recent, available=available))
            self.assertEqual('<td>David</td>' in html, included)

    def test_green_for_last_draw_loss_or_no_results_but_not_last_win(self):
        for seq, green in [('', True), ('VDE', True), ('VD', True), ('DEV', False), ('V', False)]:
            html = render_daily_pair_watch(self.data(sequence=seq))
            soup = BeautifulSoup(html, 'html.parser')
            row = soup.select_one('tbody tr')
            self.assertEqual('daily-pair-green' in row.get('class', []), green)
            if not seq:
                self.assertIn('Sin resultados hoy', row.get_text())

    def test_full_madrid_day_inverse_duplicates_calendar_and_cancelled_results(self):
        records = [perspective(1, 'V', timestamp='2026-11-23T23:00:00Z'),
                   perspective(1, 'D', player='Fox', rival='David', timestamp='2026-11-23T23:00:00Z'),
                   perspective(2, 'D', timestamp='2026-11-24T01:00:00Z'),
                   perspective(3, 'D', timestamp='2026-11-23T22:59:00Z'),
                   perspective(4, 'V', timestamp='2026-11-24T12:01:00Z'),
                   perspective(5, 'V', timestamp='2026-11-24T04:00:00Z'), {}]
        schedule = {'sources': {'GT': {'records': [
            dict(records[0], fixture_status='finished'),
            dict(perspective(6, 'E', timestamp='2026-11-24T03:00:00Z'), fixture_status='finished'),
            dict(records[5], fixture_status='cancelled', result=None)]}}}
        lookup = daily_pair_sequences(records, schedule, self.reference)
        self.assertEqual(lookup[('GT', 'david', 'fox')], 'VDE')
        self.assertEqual(lookup[('GT', 'fox', 'david')], 'DVE')

    def test_exclusions_duplicates_and_untracked_inferred_pairs(self):
        data = self.data()
        data['leagues']['GT']['groups'] *= 2
        self.assertEqual(render_daily_pair_watch(data).count('<td>David</td>'), 1)
        data['h2h_exclusions'] = [('GT', 'david', 'fox')]
        self.assertNotIn('<td>David</td>', render_daily_pair_watch(data))
        del data['h2h_exclusions']
        data['excluded_player_keys'] = [('GT', 'fox')]
        self.assertNotIn('<td>David</td>', render_daily_pair_watch(data))
        data = self.data()
        block = data['leagues']['GT']['groups'][0]['recent_h2h']['players'][0]
        data['leagues'] = {'EADRIATIC': {'groups': []}}
        data['inferred_eadriatic_players'] = [block]
        self.assertIn('<td>David</td>', render_daily_pair_watch(data))

    def test_next_hour_is_madrid_without_date_sorted_chronologically_unknown_last(self):
        data = self.data()
        players = data['leagues']['GT']['groups'][0]['recent_h2h']['players']
        template = players[0]['rivals'][0]
        players[0]['rivals'] = [dict(template, rival=name, next_match=stamp)
                                for name, stamp in [('Unknown', None), ('Late', '2026-11-24T15:30:00Z'),
                                                    ('Early', '2026-11-24T14:00:00Z')]]
        soup = BeautifulSoup(render_daily_pair_watch(data), 'html.parser')
        rows = soup.select('tbody tr')
        self.assertEqual([row.find_all('td')[2].get_text() for row in rows], ['Early', 'Late', 'Unknown'])
        self.assertEqual([row.find_all('td')[-1].get_text() for row in rows], ['15:00', '16:30', '\u2014'])
        self.assertTrue(all('daily-pair-green' in row.get('class', []) for row in rows))

    def test_official_time_priority_and_estimated_label(self):
        data = self.data()
        row = data['leagues']['GT']['groups'][0]['recent_h2h']['players'][0]['rivals'][0]
        row['inferred_pair'] = {'estimated_fixtures': [{'timestamp': '2026-11-24T16:00:00Z'}]}
        self.assertIn('17:00 (estimado)', render_daily_pair_watch(data))
        row['pair_fixtures'] = [{'timestamp': '2026-11-24T17:00:00Z'}]
        html = render_daily_pair_watch(data)
        self.assertIn('<td>18:00</td>', html)
        self.assertNotIn('17:00 (estimado)', html)

    def test_player_dot_matches_current_streaks_and_respects_league(self):
        for indicator, marker in [('GREEN', '\U0001f7e2'), ('RED', '\U0001f534'), ('NONE', ''), ('UNKNOWN', '')]:
            streaks = {'leagues': {'GT': [{'player_key': 'david', 'indicator': indicator}],
                                  'EADRIATIC': [{'player_key': 'david', 'indicator': 'RED'}]}}
            soup = BeautifulSoup(render_daily_pair_watch(self.data(), streaks), 'html.parser')
            row = soup.select_one('tbody tr')
            self.assertEqual(row.find_all('td')[1].get_text(), f'{marker} David' if marker else 'David')
            self.assertEqual(row.find_all('td')[2].get_text(), 'Fox')
            self.assertIn('daily-pair-green', row.get('class', []))
        soup = BeautifulSoup(render_daily_pair_watch(self.data()), 'html.parser')
        self.assertEqual(soup.select_one('tbody tr').find_all('td')[1].get_text(), 'David')

    def test_both_players_receive_their_own_current_streaks_dot(self):
        streaks = {'leagues': {'GT': [{'player_key': 'david', 'indicator': 'GREEN'},
                                    {'player_key': 'fox', 'indicator': 'RED'}]}}
        soup = BeautifulSoup(render_daily_pair_watch(self.data(), streaks), 'html.parser')
        cells = soup.select_one('tbody tr').find_all('td')
        self.assertEqual(cells[1].get_text(), '\U0001f7e2 David')
        self.assertEqual(cells[2].get_text(), '\U0001f534 Fox')
        streaks['leagues']['GT'][1]['indicator'] = 'NONE'
        soup = BeautifulSoup(render_daily_pair_watch(self.data(), streaks), 'html.parser')
        self.assertEqual(soup.select_one('tbody tr').find_all('td')[2].get_text(), 'Fox')

    def test_daily_sequence_is_independent_of_eight_hour_window(self):
        group = {'target': ['David', 'Fox']}
        data = {'leagues': {'GT': {'groups': [group]}}}
        records = [perspective(1, 'V', timestamp='2026-11-24T00:00:00Z')]
        attach_recent_group_h2h(data, records, self.reference)
        row = group['recent_h2h']['players'][0]['rivals'][0]
        self.assertEqual(row['current_pair_sequence'], '')
        self.assertEqual(row['daily_pair_sequence'], 'V')
        self.assertEqual(data['daily_pair_watch_date'], '2026-11-24')
        self.assertEqual(render_page(data, {}).count('id="daily-pair-watch"'), 1)
