import json
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest import mock
import uuid
import warnings

from eadriatic_leagues import parse_history_records
from gtleagues_api import build_history_records
from match_history import (
    MatchHistoryError,
    load_records,
    merge_records,
    name_key,
    perspective_id,
    update_history,
    validate_perspective_pair,
    write_records_atomic,
)


TEST_TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def workspace_tempdir():
    # Avoid tempfile cleanup ACL issues in sandboxed Windows test runners.
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield str(path)


def record(match="gt:1", player="Álex", rival="João", home_away="home", result="V"):
    return {
        "schema_version": 1,
        "league": "GT",
        "match_id": match,
        "perspective_id": perspective_id(match, player),
        "player": player.strip(),
        "player_key": name_key(player),
        "rival": rival.strip(),
        "rival_key": name_key(rival),
        "result": result,
        "timestamp": "2026-07-14T10:00:00+02:00",
        "timestamp_utc": "2026-07-14T08:00:00Z",
        "timestamp_precision": "second",
        "timezone": "UTC+02:00",
        "timezone_inferred": False,
        "home_away": home_away,
        "home_score": 2,
        "away_score": 1,
        "source_type": "gt_api",
        "source_file": "gt_api:2026-07-14",
        "data_quality": "complete",
    }


def gt_match(match_id="123", home_score=2, away_score=1, kickoff="2026-07-14T10:00:15Z"):
    return {
        "id": match_id,
        "kickoff": kickoff,
        "participants": [
            {"side": "home", "participant": {"player": {"nickname": " Álex "}}},
            {"side": "away", "participant": {"player": {"nickname": "João"}}},
        ],
        "result": {"stats": {"home_score": home_score, "away_score": away_score}},
    }


EAD_HTML = """
<html><body>
<span class="fg-heading">FC26 R475(INTERNATIONAL)13.07.2026</span>
<span class="time-heading">23:55</span>
<table><tr data-match-href="/match/44413067.html">
  <td>England (Dexter)</td><td>2 - 0<br/>(HT 1-0)</td><td>Belgium (Eric)</td>
</tr></table>
<span class="fg-heading">FC26 R476(CHAMPIONS LEAGUE)14.07.2026</span>
<span class="time-heading">00:05</span>
<table><tr data-match-href="/match/44413068.html">
  <td>Spain (Gaël)</td><td>1 - 1</td><td>France (Óscar)</td>
</tr></table>
<span class="time-heading">00:20</span>
<table><tr data-match-href="/match/44413069.html">
  <td>Spain (Gaël)</td><td>vs</td><td>France (Óscar)</td>
</tr></table>
</body></html>
"""


class MatchHistoryStoreTests(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with workspace_tempdir() as folder:
            self.assertEqual(load_records(Path(folder) / "missing.jsonl"), [])

    def test_initial_insert_and_second_run_are_idempotent(self):
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            update_history(path, [record()])
            update_history(path, [record()])
            self.assertEqual(len(load_records(path)), 1)

    def test_two_symmetric_perspectives(self):
        home = record()
        away = record(player="João", rival="Álex", home_away="away", result="D")
        validate_perspective_pair([home, away])
        self.assertEqual(len(merge_records([], [home, away])), 2)

    def test_compatible_enrichment(self):
        old = record()
        new = {**old, "competition": "League", "round": "R1"}
        merged = merge_records([old], [new])
        self.assertEqual(merged[0]["competition"], "League")

    def test_score_conflict_warns_and_keeps_existing(self):
        old = record()
        changed = {**old, "home_score": 3}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            merged = merge_records([old], [changed])
        self.assertEqual(merged[0]["home_score"], 2)
        self.assertTrue(any("home_score" in str(item.message) for item in caught))

    def test_corrupt_json_identifies_file_and_line(self):
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            path.write_text("\n{bad json}\n", encoding="utf-8")
            with self.assertRaisesRegex(MatchHistoryError, r"history\.jsonl at line 2"):
                load_records(path)

    def test_atomic_write_uses_replace_and_leaves_no_temp_file(self):
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            with mock.patch("match_history.os.replace", wraps=__import__("os").replace) as replace:
                write_records_atomic(path, [record()])
            replace.assert_called_once()
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_deterministic_order_and_stable_json_keys(self):
        later = record(match="gt:2")
        earlier = {**record(match="gt:1"), "timestamp": "2026-07-14T09:00:00+02:00", "timestamp_utc": "2026-07-14T07:00:00Z"}
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            write_records_atomic(path, [later, earlier])
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["match_id"], "gt:1")
            self.assertEqual(list(json.loads(lines[0])), sorted(json.loads(lines[0])))

    def test_unicode_nfkc_casefold_and_spaces(self):
        self.assertEqual(name_key("  ÁLEX  "), "álex")
        self.assertEqual(name_key("Ｊoão"), "joão")

    def test_trailing_empty_line_is_allowed(self):
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            write_records_atomic(path, [record()])
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n")
            self.assertEqual(len(load_records(path)), 1)


class GTAdapterTests(unittest.TestCase):
    def test_home_win_away_win_and_draw(self):
        home_win = build_history_records([gt_match()], "gt_api:test")
        away_win = build_history_records([gt_match("124", 0, 1)], "gt_api:test")
        draw = build_history_records([gt_match("125", 1, 1)], "gt_api:test")
        self.assertEqual([row["result"] for row in home_win], ["V", "D"])
        self.assertEqual([row["result"] for row in away_win], ["D", "V"])
        self.assertEqual([row["result"] for row in draw], ["E", "E"])

    def test_ids_and_z_timestamp(self):
        rows = build_history_records([gt_match()], "gt_api:test")
        self.assertEqual(rows[0]["match_id"], "gt:123")
        self.assertEqual(rows[0]["perspective_id"], "gt:123:álex")
        self.assertEqual(rows[0]["timestamp"], "2026-07-14T10:00:15+00:00")
        self.assertEqual(rows[0]["timestamp_utc"], "2026-07-14T10:00:15Z")
        self.assertFalse(rows[0]["timezone_inferred"])

    def test_timestamp_with_offset(self):
        rows = build_history_records(
            [gt_match(kickoff="2026-07-14T10:00:15+02:00")], "gt_api:test"
        )
        self.assertEqual(rows[0]["timestamp_utc"], "2026-07-14T08:00:15Z")
        self.assertEqual(rows[0]["timezone"], "UTC+02:00")

    def test_naive_timestamp_uses_documented_madrid_policy(self):
        rows = build_history_records(
            [gt_match(kickoff="2026-07-14T10:00:15")], "gt_api:test"
        )
        self.assertTrue(rows[0]["timezone_inferred"])
        self.assertEqual(rows[0]["timezone"], "Europe/Madrid")

    def test_invalid_result_or_incomplete_participants_are_skipped(self):
        invalid_result = gt_match()
        invalid_result["result"] = None
        incomplete = gt_match("124")
        incomplete["participants"] = incomplete["participants"][:1]
        self.assertEqual(build_history_records([invalid_result, incomplete], "gt_api:test"), [])

    def test_two_updates_do_not_duplicate(self):
        rows = build_history_records([gt_match()], "gt_api:test")
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            update_history(path, rows)
            update_history(path, rows)
            self.assertEqual(len(load_records(path)), 2)


class EadriaticAdapterTests(unittest.TestCase):
    def test_extracts_date_time_id_heading_and_source_order(self):
        rows = parse_history_records(EAD_HTML, "fixture.html")
        first = rows[0]
        self.assertEqual(first["match_id"], "eadriatic:44413067")
        self.assertEqual(first["timestamp"], "2026-07-13T23:55+02:00")
        self.assertEqual(first["timestamp_precision"], "minute")
        self.assertEqual(first["competition"], "INTERNATIONAL")
        self.assertEqual(first["round"], "FC26 R475")
        self.assertEqual(first["source_block_order"], 0)
        self.assertEqual(first["source_row_order"], 0)

    def test_home_win_and_draw_are_symmetric(self):
        rows = parse_history_records(EAD_HTML, "fixture.html")
        self.assertEqual([row["result"] for row in rows[:2]], ["V", "D"])
        self.assertEqual([row["result"] for row in rows[2:4]], ["E", "E"])
        validate_perspective_pair(rows[:2])
        validate_perspective_pair(rows[2:4])

    def test_away_win(self):
        html = EAD_HTML.replace("2 - 0", "0 - 2")
        rows = parse_history_records(html, "fixture.html")
        self.assertEqual([row["result"] for row in rows[:2]], ["D", "V"])

    def test_fixture_without_score_is_skipped(self):
        rows = parse_history_records(EAD_HTML, "fixture.html")
        self.assertEqual(len(rows), 4)
        self.assertNotIn("eadriatic:44413069", {row["match_id"] for row in rows})

    def test_blocks_can_move_backward_in_clock_without_using_dom_as_sort(self):
        rows = parse_history_records(EAD_HTML, "fixture.html")
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            update_history(path, list(reversed(rows)))
            stored = load_records(path)
        self.assertEqual(stored[0]["match_id"], "eadriatic:44413067")
        self.assertEqual(stored[-1]["match_id"], "eadriatic:44413068")

    def test_two_updates_do_not_duplicate(self):
        rows = parse_history_records(EAD_HTML, "fixture.html")
        with workspace_tempdir() as folder:
            path = Path(folder) / "history.jsonl"
            update_history(path, rows)
            update_history(path, rows)
            self.assertEqual(len(load_records(path)), 4)


if __name__ == "__main__":
    unittest.main()
