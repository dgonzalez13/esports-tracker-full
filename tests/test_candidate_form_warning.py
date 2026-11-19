import unittest
from datetime import datetime, timedelta, timezone

from tests.test_bet_candidates import CandidateTests
from tests.test_underdog_matchups import UnderdogMatchupTests
from tests.test_h2h_analysis import perspective
from web_tracker.generate_site import render_bet_candidates, attach_recent_group_h2h, candidate_form_warning


class FormWarningTests(unittest.TestCase):
    def form(self, player, indicator, wins, losses):
        return dict(league='GT', player_key=player, indicator=indicator, wins=wins, losses=losses,
                    played=10, loss_pct=losses*10, win_pct=wins*10)

    def test_warning_in_all_horizons_without_hiding_candidate_or_statistics(self):
        for horizon in (4, 5, 6):
            data, rival = UnderdogMatchupTests().data()
            rival.update(CandidateTests().rival())
            for row in rival['pair_stats']['pair_horizons']:
                if row['horizon'] < horizon:
                    row['win_pct'] = 80
            data['candidate_form'] = [self.form('david', 'RED', 1, 7), self.form('fox', 'GREEN', 6, 1)]
            html = render_bet_candidates(data)
            self.assertIn('ALERTA: evitar apostar por David', html)
            self.assertIn('7/10 derrotas (70.00%)', html)
            self.assertIn('6/10 victorias (60.00%)', html)
            self.assertEqual(html.count('GT David - Fox'), 1)
            self.assertIn('data-first-match="true"', html)

    def test_no_warning_for_other_combinations_missing_form_or_other_league(self):
        for a, b in [('GREEN', 'RED'), ('RED', 'RED'), ('NONE', 'GREEN'), ('RED', 'NONE')]:
            data = {'candidate_form': [self.form('david', a, 2, 6), self.form('fox', b, 6, 2)]}
            self.assertEqual(candidate_form_warning(data, 'GT', 'David', 'Fox'), '')
        self.assertEqual(candidate_form_warning({}, 'GT', 'David', 'Fox'), '')
        self.assertEqual(candidate_form_warning(data, 'EADRIATIC', 'David', 'Fox'), '')

    def test_attached_form_uses_all_recent_opponents_and_ignores_old_and_future(self):
        ref = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
        records = [perspective(1, 'D', timestamp=(ref-timedelta(minutes=30)).isoformat()),
                   perspective(1, 'V', player='Fox', rival='David', timestamp=(ref-timedelta(minutes=30)).isoformat()),
                   perspective(2, 'D', rival='Other', timestamp=(ref-timedelta(minutes=15)).isoformat()),
                   perspective(3, 'V', timestamp=(ref-timedelta(hours=9)).isoformat()),
                   perspective(4, 'V', timestamp=(ref+timedelta(minutes=1)).isoformat())]
        data = {}
        attach_recent_group_h2h(data, records, ref)
        self.assertIn('2/2 derrotas (100.00%)', candidate_form_warning(data, 'GT', 'David', 'Fox'))
        attach_recent_group_h2h(data, records, ref+timedelta(hours=10))
        self.assertEqual(candidate_form_warning(data, 'GT', 'David', 'Fox'), '')
