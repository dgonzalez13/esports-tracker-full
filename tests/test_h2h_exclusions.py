import json
import uuid
import unittest
from pathlib import Path
from h2h_exclusions import PREFIX, load_h2h_exclusions
from selected_players import load_tracked_players
from update_tracked_players import rewrite_tracked_players
from web_tracker.generate_site import render_recent_group_h2h_dashboard


class ExclusionTests(unittest.TestCase):
    def test_manual_format_without_member_list(self):
        path = Path(__file__).resolve().parent / ('.h2h-' + uuid.uuid4().hex + '.txt')
        try:
            directive = dict(league='GT', group=1, player='A', rival='B')
            path.write_text('GT|A\nGT|B\nGT|C\nGT|D\nGT|E\n' + PREFIX + json.dumps(directive) + '\n', encoding='utf-8')
            self.assertEqual(load_h2h_exclusions(path), {('GT', 'a', 'b')})
            self.assertEqual(len(load_tracked_players(path)), 5)
        finally:
            path.unlink(missing_ok=True)

    def test_direction_persistence_and_group_update_cleanup(self):
        path = Path(__file__).resolve().parent / ('.h2h-' + uuid.uuid4().hex + '.txt')
        try:
            lines = [f'{league}|{league}{i}' for league in ('EADRIATIC', 'GT') for i in range(10)]
            first = dict(league='GT', group=1, player='GT0', rival='GT1', members=[f'GT{i}' for i in range(5)])
            second = dict(league='GT', group=2, player='GT5', rival='GT6', members=[f'GT{i}' for i in range(5, 10)])
            path.write_text('\n'.join(lines + [PREFIX + json.dumps(first), PREFIX + json.dumps(second)]) + '\n', encoding='utf-8')
            self.assertEqual(len(load_tracked_players(path)), 20)
            self.assertIn(('GT', 'gt0', 'gt1'), load_h2h_exclusions(path))
            self.assertNotIn(('GT', 'gt1', 'gt0'), load_h2h_exclusions(path))
            rewrite_tracked_players(path, {('GT', 1): tuple(first['members'])})
            self.assertNotIn(('GT', 'gt0', 'gt1'), load_h2h_exclusions(path))
            self.assertIn(('GT', 'gt5', 'gt6'), load_h2h_exclusions(path))
            changed = path.read_text(encoding='utf-8').replace('GT|GT5\n', 'GT|New\n')
            path.write_text(changed, encoding='utf-8')
            self.assertEqual(load_h2h_exclusions(path), set())
        finally:
            path.unlink(missing_ok=True)

    def test_only_highlighted_direction_is_filtered(self):
        rival = dict(rival='B', played=2, wins=0, historical_win_pct=42, sequence='DD')
        data = {'h2h_exclusions': [('GT', 'a', 'b')], 'leagues': {'GT': {'groups': [
            {'recent_h2h': {'players': [{'player': 'A', 'rivals': [rival]}]}}
        ]}}}
        html = render_recent_group_h2h_dashboard(data)
        self.assertIn('No hay enfrentamientos destacados.', html)
        self.assertNotIn('<td>A</td>', html)


if __name__ == '__main__':
    unittest.main()
