import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
import os
from unittest.mock import patch
from import_eadriatic_inbox import main as import_main
from web_tracker.generate_site import render_first_win_followups, render_first_win_window_candidates

from tests.test_bet_candidates import CandidateTests
from tests.test_first_win_window_candidates import WindowCandidateTests
from web_tracker.eadriatic_inference import (estimate_pair_schedule, parse_start_inputs,
                                             save_starts, load_starts, OFFSETS)
from web_tracker.bet_candidates import candidate, first_win_window_candidate


class EstimatedScheduleTests(unittest.TestCase):
    first = datetime(2026, 11, 19, 6, tzinfo=timezone.utc)  # 07:00 Madrid
    pair = ('david', 'fox')

    def estimate(self, offsets, starts=(), reference=None):
        stamps = [self.first + timedelta(minutes=offset) for offset in offsets]
        return estimate_pair_schedule(stamps, reference or stamps[-1] + timedelta(minutes=15), self.pair, starts)

    def test_exact_user_pattern_and_automatic_anchor(self):
        result = self.estimate([0, 75, 165])
        self.assertIn('pauta observada', result['estimate_status'])
        self.assertEqual([f['match_number'] for f in result['estimated_fixtures']], [4, 5, 6])
        self.assertEqual([f['timestamp'] for f in result['estimated_fixtures']],
                         [(self.first + timedelta(minutes=m)).isoformat() for m in [240, 315, 390]])

    def test_one_or_two_observations_do_not_assume_first_match(self):
        for offsets in ([0], [0, 75]):
            self.assertEqual(self.estimate(offsets)['estimated_fixtures'], [])

    def test_manual_start_allows_schedule_after_one_result(self):
        starts = parse_start_inputs('David|Fox|2026-11-19 07:00')
        result = self.estimate([0], starts)
        local = [datetime.fromisoformat(f['timestamp']).astimezone(datetime.fromisoformat(starts[0]['start']).tzinfo).strftime('%H:%M')
                 for f in result['estimated_fixtures']]
        self.assertEqual(local, ['08:15', '09:45', '11:00', '12:15', '13:30'])
        self.assertIn('manual', result['estimate_status'])

    def test_missing_results_and_irregular_timing_do_not_shift_sequence(self):
        starts = parse_start_inputs('David|Fox|2026-11-19 07:00')
        for offsets in ([75, 165], [0, 165], [0, 74, 165]):
            self.assertEqual(self.estimate(offsets, starts)['estimated_fixtures'], [])

    def test_past_estimated_slot_remains_pending_without_result(self):
        starts = parse_start_inputs('David|Fox|2026-11-19 07:00')
        result = self.estimate([0], starts, self.first + timedelta(minutes=200))
        self.assertEqual(len(result['estimated_fixtures']), 5)
        self.assertTrue(result['estimated_fixtures'][0]['started'])
        rival = CandidateTests().rival()
        rival.update(pair_fixtures=[], current_pair_sequence='D', inferred_pair=result)
        line = candidate(rival, 4, league='EADRIATIC')[1]
        self.assertTrue(line.startswith('[2] 20 '))
        self.assertIn('08:15', line)
        self.assertIn('Hora estimada pasada', line)
        self.assertEqual(rival['current_pair_sequence'], 'D')

    def test_repeat_victory_uses_estimates_and_official_schedule_wins(self):
        starts = parse_start_inputs('David|Fox|2026-11-19 07:00')
        estimate = self.estimate([0], starts)
        rival = WindowCandidateTests().rival()
        for row in rival['pair_stats']['first_win_followups']:
            row['league'] = 'EADRIATIC'
        rival.update(pair_fixtures=[], inferred_pair=estimate)
        line = first_win_window_candidate(rival, 'EADRIATIC')[1]
        self.assertIn('Horario estimado', line)
        self.assertIn('08:15', line)
        rival['pair_fixtures'] = [{'timestamp': self.first.isoformat(), 'started': False}]
        self.assertNotIn('Horario estimado', first_win_window_candidate(rival, 'EADRIATIC')[1])

    def test_start_config_dry_run_update_and_validation(self):
        path = Path(__file__).parent / '.tmp' / f'starts-{uuid.uuid4().hex}.json'
        entries = parse_start_inputs('David|Fox|2026-11-19 07:00;A|B|2026-11-19 08:00')
        try:
            self.assertTrue(save_starts(entries, path))
            self.assertFalse(path.exists())
            save_starts(entries, path, apply=True)
            self.assertEqual(load_starts(path), entries)
            self.assertFalse(save_starts(entries, path, apply=True))
            for invalid in ('David|David|2026-11-19 07:00', 'David|Fox', 'David|Fox|tomorrow'):
                with self.assertRaises(ValueError):
                    parse_start_inputs(invalid)
        finally:
            path.unlink(missing_ok=True)

    def test_imported_pair_is_in_repeat_table_and_candidates_outside_groups(self):
        starts = parse_start_inputs('David|Fox|2026-11-19 07:00')
        rival = WindowCandidateTests().rival()
        rival.update(pair_fixtures=[], inferred_pair=self.estimate([0], starts),
                     historical_played=100, historical_wins=50, historical_losses=20)
        for row in rival['pair_stats']['first_win_followups']:
            row.update(league='EADRIATIC', first_win_series=20)
        data = {'leagues': {'EADRIATIC': {'groups': []}},
                'inferred_eadriatic_players': [{'player': 'David', 'rivals': [rival]}]}
        table = render_first_win_followups(data)
        self.assertIn('<td>EADRIATIC</td>', table)
        self.assertIn('<td>David</td>', table)
        self.assertIn('Estimado', table)
        self.assertIn('EADRIATIC David - B', render_first_win_window_candidates(data))

    def test_workflow_start_only_change_regenerates_without_new_results(self):
        root = Path(__file__).parent / '.tmp'
        path = root / f'starts-{uuid.uuid4().hex}.json'
        report = root / f'report-{uuid.uuid4().hex}.json'
        try:
            with patch('sys.argv', ['import', '--estimated-starts-file', str(path), '--report', str(report)]), \
                 patch.dict(os.environ, {'FIRST_GAMES': 'David|Fox|2026-11-19 07:00', 'APPLY_IMPORT': 'true'}, clear=True), \
                 patch('import_eadriatic_inbox.import_inbox', return_value={'changed': False}), patch('builtins.print'):
                import_main()
            self.assertTrue(path.exists())
            self.assertIn('"changed": true', report.read_text(encoding='utf-8'))
        finally:
            path.unlink(missing_ok=True)
            report.unlink(missing_ok=True)

    def test_midnight_schedule_keeps_correct_dates(self):
        first = self.first.replace(hour=22)
        starts = parse_start_inputs('David|Fox|2026-11-19 23:00')
        result = estimate_pair_schedule([first, first + timedelta(minutes=75)],
                                        first + timedelta(minutes=90), self.pair, starts)
        self.assertEqual(datetime.fromisoformat(result['estimated_fixtures'][-1]['timestamp']).day, 20)
