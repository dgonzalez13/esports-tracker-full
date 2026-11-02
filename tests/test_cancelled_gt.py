from datetime import datetime, timedelta, timezone
import unittest

from fixture_schedule import parse_gt_fixtures
from gtleagues_api import build_history_records, process
from tests.test_match_history import gt_match
from tests.test_bet_candidates import CandidateTests
from tests.test_underdog_matchups import UnderdogMatchupTests
from web_tracker.bet_candidates import candidate
from web_tracker.pair_series_schedule import pair_series_schedule, cancelled_pair_counts
from web_tracker.upcoming_matches import upcoming_fixtures
from web_tracker.generate_site import attach_recent_group_h2h, render_underdog_matchups


class CancelledGTTests(unittest.TestCase):
    reference = datetime(2026, 11, 2, 5, 5, tzinfo=timezone.utc)

    def schedule(self):
        fixtures = []
        for i in range(6):
            row = gt_match()
            row.update(id=str(i), status=4 if i == 0 else 0,
                       kickoff=(self.reference + timedelta(minutes=75*i-5)).isoformat())
            fixtures.append(row)
        return {'sources': {'GT': {'records': parse_gt_fixtures(fixtures)}}}

    def test_cancelled_is_not_unknown_or_a_result_even_with_provisional_score(self):
        row = gt_match()
        row['status'] = 4
        parsed = parse_gt_fixtures([row])
        self.assertEqual(len(parsed), 2)
        self.assertTrue(all(r['fixture_status'] == 'cancelled' and r['result'] is None for r in parsed))
        self.assertEqual(build_history_records([row], 'test'), [])
        self.assertEqual(process([row]), {})

    def test_cancelled_slot_does_not_enter_sequence_or_upcoming(self):
        schedule = self.schedule()
        rows = schedule['sources']['GT']['records']
        a, b = rows[0]['player_key'], rows[0]['rival_key']
        stale_final = dict(rows[0], result='V')
        sequences, pending = pair_series_schedule([stale_final], schedule, self.reference)
        self.assertNotIn(('GT', a, b), sequences)
        self.assertEqual(len(pending[('GT', tuple(sorted((a, b))))]), 5)
        self.assertEqual(len(upcoming_fixtures(schedule, self.reference)), 5)
        self.assertEqual(cancelled_pair_counts(schedule, self.reference)[('GT', tuple(sorted((a, b))))], 1)

    def test_five_effective_games_start_at_one_and_do_not_request_sixth(self):
        rival = CandidateTests().rival()
        rival.update(pair_cancelled=1, pair_fixtures=rival['pair_fixtures'][:5])
        line = candidate(rival, 6)[1]
        self.assertTrue(line.startswith('[1] 3 '))
        self.assertNotIn('Faltan', line)
        self.assertIn('máximo 5', line)
        rival['current_pair_sequence'] = 'DDDDD'
        self.assertIsNone(candidate(rival, 6))
        rival['current_pair_sequence'] = 'DD'
        self.assertTrue(candidate(rival, 6)[1].startswith('[3] 12 '))

    def test_cancellation_attached_and_not_reported_as_started(self):
        schedule = self.schedule()
        rows = schedule['sources']['GT']['records']
        a, b = rows[0]['player'], rows[0]['rival']
        group = {'target': [a, b], 'h2h_matrix': [
            {'player': a, 'rivals': [{'rival': b, 'matches': 100, 'W': 40, 'L': 30, 'win_pct': 40}]}]}
        data = {'leagues': {'GT': {'groups': [group]}}}
        attach_recent_group_h2h(data, [], self.reference, schedule)
        rival = group['recent_h2h']['players'][0]['rivals'][0]
        self.assertEqual(rival['pair_cancelled'], 1)
        self.assertFalse(rival['match_started'])
        self.assertEqual(rival['current_pair_sequence'], '')
        self.assertNotIn('Faltan', render_underdog_matchups(data))


if __name__ == '__main__':
    unittest.main()
