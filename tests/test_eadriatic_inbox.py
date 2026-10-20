import json
from pathlib import Path
import unittest

from import_eadriatic_inbox import import_inbox
from tests.test_eadriatic_saved_results import HTML
from tests.test_match_history import workspace_tempdir


class InboxTests(unittest.TestCase):
    def setup_inbox(self, folder):
        root = Path(folder)
        inbox = root / 'inbox'
        inbox.mkdir()
        return inbox, root / 'history.jsonl', root / 'log.json'

    def test_preview_has_no_persistent_effect(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            (inbox / '20261019_p007.html').write_text(HTML, encoding='utf-8')
            report = import_inbox(inbox, history, ledger)
            self.assertEqual(report['import']['added_matches'], 1)
            self.assertFalse(history.exists())
            self.assertFalse(ledger.exists())

    def test_delete_processed_pages_keeps_history_and_log(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            page = inbox / '20261019_p007.html'
            page.write_text(HTML, encoding='utf-8')
            report = import_inbox(inbox, history, ledger, apply=True)
            self.assertTrue(report['changed'])
            before = history.read_bytes(), ledger.read_bytes()
            page.unlink()
            empty = import_inbox(inbox, history, ledger, apply=True)
            self.assertFalse(empty['changed'])
            self.assertEqual((history.read_bytes(), ledger.read_bytes()), before)
            (inbox / 'renamed.html').write_text(HTML, encoding='utf-8')
            same = import_inbox(inbox, history, ledger, apply=True)
            self.assertFalse(same['changed'])
            self.assertEqual(same['files_already_processed'], 1)
            self.assertEqual(len(json.loads(ledger.read_text(encoding='utf-8'))['processed_files']), 1)

    def test_only_top_level_supported_files_are_considered(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            (Path(folder) / 'outside.html').write_text('not a result page', encoding='utf-8')
            (inbox / 'README.md').write_text('instructions', encoding='utf-8')
            sub = inbox / 'assets'
            sub.mkdir()
            (sub / 'nested.html').write_text('not a result page', encoding='utf-8')
            report = import_inbox(inbox, history, ledger, apply=True)
            self.assertEqual(report['files_present'], 0)
            self.assertFalse(history.exists())

    def test_equal_files_in_same_batch_are_imported_once(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            for filename in ('a.html', 'b.html'):
                (inbox / filename).write_text(HTML, encoding='utf-8')
            report = import_inbox(inbox, history, ledger, apply=True)
            self.assertEqual(report['files_pending'], 1)
            self.assertEqual(len(history.read_text(encoding='utf-8').splitlines()), 2)

    def test_invalid_page_does_not_mark_any_file_as_imported(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            (inbox / 'good.html').write_text(HTML, encoding='utf-8')
            (inbox / 'bad.html').write_text('<html>invalid</html>', encoding='utf-8')
            with self.assertRaises(ValueError):
                import_inbox(inbox, history, ledger, apply=True)
            self.assertFalse(history.exists())
            self.assertFalse(ledger.exists())

    def test_complete_day_can_be_rebuilt_after_pages_were_processed(self):
        with workspace_tempdir() as folder:
            inbox, history, ledger = self.setup_inbox(folder)
            (inbox / 'page.html').write_text(HTML, encoding='utf-8')
            import_inbox(inbox, history, ledger, apply=True)
            daily = history.parent / '20261019_eadriatic_player_stats.txt'
            self.assertFalse(daily.exists())
            report = import_inbox(inbox, history, ledger, apply=True, complete_days=['2026-10-19'])
            self.assertTrue(daily.exists())
            self.assertEqual(report['import']['added_matches'], 0)
            self.assertEqual(report['import']['daily_stats_rebuilt'], ['2026-10-19'])


if __name__ == '__main__':
    unittest.main()
