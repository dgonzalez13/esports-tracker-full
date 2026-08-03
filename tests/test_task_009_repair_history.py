from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

from match_history import MatchHistoryError, load_records
from repair_eadriatic_day import (
    parse_target_date, save_txt_for_date, update_repaired_history,
)
from eadriatic_leagues import build_df, parse_matches, process


HTML = """
<span class="fg-heading">FC26 R1(INTERNATIONAL)03.08.2026</span>
<span class="time-heading">23:45</span>
<table><tr data-match-href="/match/9001.html">
<td>Club (Lucas)</td><td>3 - 1</td><td>Club (Fox)</td></tr></table>
<span class="time-heading">23:58</span>
<table><tr data-match-href="/match/9002.html">
<td>Club (Kratos)</td><td>2 - 2</td><td>Club (Atlas)</td></tr></table>
"""

INCOMPLETE_HTML = """
<span class="fg-heading">FC26 R1(INTERNATIONAL)03.08.2026</span>
<table><tr data-match-href="/match/9003.html">
<td>Club (Lost)</td><td>0 - 1</td><td>Club (Snake)</td></tr></table>
"""


class RepairHistoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / ".tmp" / uuid.uuid4().hex
        self.root.mkdir()
        self.history = self.root / "match_history.jsonl"

    def tearDown(self):
        for child in self.root.iterdir():
            child.unlink()
        self.root.rmdir()

    def update(self, html=HTML, target=datetime(2026, 8, 3)):
        return update_repaired_history(
            html, target, history_path=self.history,
            collected_at="2026-08-04T00:10:00+02:00",
        )

    def test_new_history_perspectives_ids_utc_timezone_and_explicit_date(self):
        summary = self.update()
        rows = load_records(self.history)
        self.assertEqual(summary["added_perspectives"], 4)
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["perspective_id"] for row in rows}, {
            "eadriatic:9001:lucas", "eadriatic:9001:fox",
            "eadriatic:9002:kratos", "eadriatic:9002:atlas",
        })
        self.assertTrue(all(row["timestamp_utc"].endswith("Z") for row in rows))
        self.assertTrue(all(row["timezone"] == "Europe/Madrid" for row in rows))
        self.assertTrue(all(row["timezone_inferred"] is True for row in rows))
        self.assertTrue(all(row["timestamp"].startswith("2026-08-03") for row in rows))

    def test_txt_and_jsonl_are_updated_together(self):
        matches = parse_matches(HTML)
        df, vs = build_df(process(matches))
        with patch("repair_eadriatic_day.os.path.join", return_value=str(self.root / "daily.txt")), patch("builtins.print"):
            save_txt_for_date(df, vs, datetime(2026, 8, 3))
        self.update()
        self.assertTrue((self.root / "daily.txt").exists())
        self.assertTrue(self.history.exists())

    def test_second_run_is_idempotent_and_does_not_touch_file(self):
        first = self.update()
        before = self.history.read_bytes()
        second = self.update()
        self.assertEqual(first["added_perspectives"], 4)
        self.assertEqual(second["added_perspectives"], 0)
        self.assertEqual(second["duplicate_perspectives"], 4)
        self.assertEqual(self.history.read_bytes(), before)

    def test_existing_history_adds_only_new_perspectives(self):
        self.update(HTML.replace("9002", "8002"))
        summary = self.update()
        self.assertEqual(summary["added_perspectives"], 2)
        self.assertEqual(len(load_records(self.history)), 6)

    def test_incomplete_match_is_omitted_without_inventing_fields(self):
        summary = self.update(INCOMPLETE_HTML)
        self.assertEqual(summary["txt_matches"], 1)
        self.assertEqual(summary["generated_perspectives"], 0)
        self.assertEqual(summary["omitted_matches"], 1)
        self.assertNotIn("eadriatic:9003", {row["match_id"] for row in load_records(self.history)})

    def test_no_reliable_records_does_not_create_or_modify_jsonl(self):
        summary = self.update("<html></html>")
        self.assertEqual(summary["added_perspectives"], 0)
        self.assertFalse(self.history.exists())
        self.update()
        before = self.history.read_bytes()
        update_repaired_history("<html></html>", datetime(2026, 8, 3), history_path=self.history)
        self.assertEqual(self.history.read_bytes(), before)

    def test_malformed_jsonl_is_reported_and_preserved(self):
        self.history.write_text("not-json\n", encoding="utf-8")
        before = self.history.read_bytes()
        with self.assertRaises(MatchHistoryError):
            self.update()
        self.assertEqual(self.history.read_bytes(), before)

    def test_date_formats_and_after_midnight_default(self):
        self.assertEqual(parse_target_date("20260803").strftime("%Y-%m-%d"), "2026-08-03")
        self.assertEqual(parse_target_date("03082026").strftime("%Y-%m-%d"), "2026-08-03")
        after_midnight = datetime(2026, 8, 4, 0, 5)
        self.assertEqual(parse_target_date(now=after_midnight).strftime("%Y-%m-%d"), "2026-08-03")

    def test_other_day_records_are_not_persisted(self):
        summary = self.update(target=datetime(2026, 8, 2))
        self.assertEqual(summary["added_perspectives"], 0)
        self.assertFalse(self.history.exists())


if __name__ == "__main__":
    unittest.main()
