import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import uuid

from history_query import (
    HistoryQueryError,
    duplicate_perspective_ids,
    filter_by_league,
    filter_by_time,
    head_to_head,
    latest_matches,
    load_all_history,
    load_history,
    player_history,
    player_vs_rival,
)
from match_history import name_key


TEST_TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def temporary_folder():
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield path


def make_record(
    perspective_id="gt:1:david",
    timestamp="2026-07-14T08:00:00Z",
    player="David",
    rival="Fox",
    league="GT",
    match_id="gt:1",
):
    return {
        "timestamp_utc": timestamp,
        "timestamp": timestamp,
        "match_id": match_id,
        "player": player,
        "player_key": name_key(player),
        "rival": rival,
        "rival_key": name_key(rival),
        "league": league,
        "perspective_id": perspective_id,
    }


def write_jsonl(path, values, blank_lines=False):
    lines = [json.dumps(value, ensure_ascii=False) for value in values]
    separator = "\n\n" if blank_lines else "\n"
    Path(path).write_text(separator.join(lines) + "\n", encoding="utf-8")


class LoadHistoryTests(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        with temporary_folder() as folder:
            self.assertEqual(load_history(folder / "missing.jsonl"), [])

    def test_empty_file_returns_empty_list(self):
        with temporary_folder() as folder:
            path = folder / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            self.assertEqual(load_history(path), [])

    def test_blank_lines_are_ignored(self):
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            path.write_text("\n" + json.dumps(make_record()) + "\n\n", encoding="utf-8")
            self.assertEqual(len(load_history(path)), 1)

    def test_valid_jsonl_is_loaded(self):
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, [make_record()])
            self.assertEqual(load_history(path)[0]["player"], "David")

    def test_invalid_json_reports_path_line_and_cause(self):
        with temporary_folder() as folder:
            path = folder / "bad.jsonl"
            path.write_text("\n{bad}\n", encoding="utf-8")
            with self.assertRaises(HistoryQueryError) as caught:
                load_history(path)
            message = str(caught.exception)
            self.assertIn(str(path), message)
            self.assertIn("line 2", message)
            self.assertIsNotNone(caught.exception.__cause__)

    def test_non_object_json_is_rejected(self):
        for value in ([], "text", 3, None):
            with self.subTest(value=value), temporary_folder() as folder:
                path = folder / "bad.jsonl"
                write_jsonl(path, [value])
                with self.assertRaisesRegex(HistoryQueryError, r"line 1"):
                    load_history(path)

    def test_results_are_chronological(self):
        late = make_record("gt:2:fox", "2026-07-14T09:00:00Z", match_id="gt:2")
        early = make_record()
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, [late, early])
            self.assertEqual([r["match_id"] for r in load_history(path)], ["gt:1", "gt:2"])

    def test_identifier_tie_breakers_are_deterministic(self):
        records = [
            make_record("gt:2:z", match_id="gt:2", player="Zed"),
            make_record("gt:1:b", match_id="gt:1", player="Beta"),
            make_record("gt:1:a", match_id="gt:1", player="Alpha"),
        ]
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, records)
            self.assertEqual(
                [r["perspective_id"] for r in load_history(path)],
                ["gt:1:a", "gt:1:b", "gt:2:z"],
            )

    def test_string_and_path_inputs(self):
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, [make_record()])
            self.assertEqual(load_history(str(path)), load_history(path))

    def test_combined_history_is_resorted_and_allows_missing_file(self):
        gt = make_record("gt:2:david", "2026-07-14T09:00:00Z", match_id="gt:2")
        ead = make_record(
            "eadriatic:1:eric", "2026-07-14T08:00:00Z", "Eric", "Dexter",
            "EADRIATIC", "eadriatic:1",
        )
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            ead_path = folder / "ead.jsonl"
            write_jsonl(gt_path, [gt])
            write_jsonl(ead_path, [ead])
            combined = load_all_history(gt_path, ead_path)
            self.assertEqual([r["league"] for r in combined], ["EADRIATIC", "GT"])
            self.assertEqual(len(load_all_history(gt_path, folder / "missing")), 1)

    def test_missing_sort_fields_are_safe(self):
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, [{"player": "Unknown"}, make_record()])
            self.assertEqual(len(load_history(path)), 2)


class LeagueAndNameTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            make_record(),
            make_record("gt:1:fox", player="Fox", rival="David"),
            make_record(
                "eadriatic:2:david", player="David", rival="Eric",
                league="EADRIATIC", match_id="eadriatic:2",
            ),
        ]

    def test_league_filter_is_case_and_space_insensitive(self):
        self.assertEqual(len(filter_by_league(self.records, " gt ")), 2)

    def test_empty_or_non_string_league_is_rejected(self):
        for value in ("", "  ", None, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                filter_by_league(self.records, value)

    def test_future_league_is_not_artificially_rejected(self):
        record = make_record(league="FUTURE")
        self.assertEqual(len(filter_by_league([record], "future")), 1)

    def test_player_history_uses_player_key(self):
        self.assertEqual(len(player_history(self.records, "David")), 2)

    def test_player_appearing_only_as_rival_is_not_included(self):
        self.assertEqual(player_history([self.records[0]], "Fox"), [])

    def test_player_spaces_are_normalized(self):
        self.assertEqual(len(player_history(self.records, "  David  ")), 2)

    def test_unicode_normalization_reuses_match_history_rules(self):
        record = make_record(player="Álex", rival="João")
        self.assertEqual(len(player_history([record], "  ÁLEX ")), 1)

    def test_optional_league_filter(self):
        self.assertEqual(len(player_history(self.records, "David", league="GT")), 1)

    def test_empty_player_is_rejected(self):
        for value in ("", "  ", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                player_history(self.records, value)


class RivalAndHeadToHeadTests(unittest.TestCase):
    def setUp(self):
        self.david = make_record()
        self.fox = make_record("gt:1:fox", player="Fox", rival="David")
        self.other = make_record(
            "gt:2:david", "2026-07-14T09:00:00Z", player="David", rival="Wolf",
            match_id="gt:2",
        )
        self.records = [self.other, self.fox, self.david]

    def test_player_vs_rival_returns_one_direction(self):
        result = player_vs_rival(self.records, "David", "Fox")
        self.assertEqual([row["player"] for row in result], ["David"])

    def test_head_to_head_returns_both_directions(self):
        result = head_to_head(self.records, "David", "Fox")
        self.assertEqual({row["player"] for row in result}, {"David", "Fox"})

    def test_other_rivals_are_excluded(self):
        self.assertEqual(len(head_to_head(self.records, "David", "Fox")), 2)

    def test_rival_filters_support_optional_league(self):
        other_league = {**self.david, "league": "EADRIATIC"}
        result = player_vs_rival([self.david, other_league], "David", "Fox", "GT")
        self.assertEqual(len(result), 1)

    def test_empty_names_are_rejected(self):
        calls = (
            lambda: player_vs_rival(self.records, "", "Fox"),
            lambda: player_vs_rival(self.records, "David", " "),
            lambda: head_to_head(self.records, "", "Fox"),
            lambda: head_to_head(self.records, "David", None),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


class TimeFilterTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            make_record("gt:1:a", "2026-07-14T08:00:00Z", match_id="gt:1"),
            make_record("gt:2:a", "2026-07-14T09:00:00Z", match_id="gt:2"),
            make_record("gt:3:a", "2026-07-14T10:00:00Z", match_id="gt:3"),
        ]

    def test_start_bound(self):
        self.assertEqual(len(filter_by_time(self.records, start="2026-07-14T09:00:00Z")), 2)

    def test_end_bound(self):
        self.assertEqual(len(filter_by_time(self.records, end="2026-07-14T09:00:00Z")), 2)

    def test_range_is_inclusive(self):
        result = filter_by_time(
            self.records, "2026-07-14T09:00:00Z", "2026-07-14T09:00:00Z"
        )
        self.assertEqual([row["match_id"] for row in result], ["gt:2"])

    def test_z_suffix_is_accepted(self):
        self.assertEqual(len(filter_by_time(self.records, start="2026-07-14T10:00:00Z")), 1)

    def test_aware_datetime_is_normalized_to_utc(self):
        bound = datetime(2026, 7, 14, 11, 0, tzinfo=timezone(timedelta(hours=2)))
        result = filter_by_time(self.records, start=bound, end=bound)
        self.assertEqual([row["match_id"] for row in result], ["gt:2"])

    def test_naive_datetime_is_interpreted_as_utc(self):
        bound = datetime(2026, 7, 14, 9, 0)
        result = filter_by_time(self.records, start=bound, end=bound)
        self.assertEqual([row["match_id"] for row in result], ["gt:2"])

    def test_inverted_range_is_rejected(self):
        with self.assertRaises(ValueError):
            filter_by_time(
                self.records, "2026-07-14T10:00:00Z", "2026-07-14T09:00:00Z"
            )

    def test_invalid_time_string_is_rejected(self):
        with self.assertRaises(ValueError):
            filter_by_time(self.records, start="not-a-date")

    def test_missing_or_invalid_timestamp_is_excluded_with_bounds(self):
        records = [*self.records, {"perspective_id": "missing"}, {"timestamp_utc": "bad"}]
        self.assertEqual(len(filter_by_time(records, start="2026-07-14T00:00:00Z")), 3)

    def test_no_bounds_preserves_records_without_timestamp(self):
        records = [*self.records, {"perspective_id": "missing"}]
        self.assertEqual(len(filter_by_time(records)), 4)

    def test_custom_time_field(self):
        record = {"custom": "2026-07-14T09:00:00Z", "perspective_id": "custom"}
        self.assertEqual(
            len(filter_by_time([record], start="2026-07-14T09:00:00Z", field="custom")), 1
        )


class LatestMatchesTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            make_record(
                f"gt:{index}:david", f"2026-07-14T{index:02d}:00:00Z",
                player="David" if index % 2 else "Fox",
                league="GT" if index < 4 else "EADRIATIC", match_id=f"gt:{index}",
            )
            for index in range(1, 6)
        ]

    def test_latest_n_perspectives(self):
        self.assertEqual(len(latest_matches(self.records, 2)), 2)

    def test_subset_remains_ascending(self):
        result = latest_matches(list(reversed(self.records)), 2)
        self.assertEqual([r["match_id"] for r in result], ["gt:4", "gt:5"])

    def test_player_is_filtered_first(self):
        result = latest_matches(self.records, 2, player="David")
        self.assertEqual([r["match_id"] for r in result], ["gt:3", "gt:5"])

    def test_league_is_filtered_first(self):
        result = latest_matches(self.records, 2, league="GT")
        self.assertEqual([r["match_id"] for r in result], ["gt:2", "gt:3"])

    def test_zero_limit(self):
        self.assertEqual(latest_matches(self.records, 0), [])

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            latest_matches(self.records, -1)

    def test_non_integer_limit_is_rejected(self):
        for value in (1.5, "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                latest_matches(self.records, value)

    def test_boolean_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            latest_matches(self.records, True)

    def test_limit_larger_than_available(self):
        self.assertEqual(len(latest_matches(self.records, 50)), len(self.records))


class DuplicateAndImmutabilityTests(unittest.TestCase):
    def test_duplicate_ids_are_identified_once_and_sorted(self):
        records = [
            {"perspective_id": "z"}, {"perspective_id": "a"},
            {"perspective_id": "z"}, {"perspective_id": "a"},
            {"perspective_id": "a"},
        ]
        self.assertEqual(duplicate_perspective_ids(records), ["a", "z"])

    def test_invalid_ids_are_ignored(self):
        records = [
            {}, {"perspective_id": ""}, {"perspective_id": None},
            {"perspective_id": 2}, {"perspective_id": []},
        ]
        self.assertEqual(duplicate_perspective_ids(records), [])

    def test_queries_do_not_modify_input_or_order(self):
        records = [make_record("gt:2:a", match_id="gt:2"), make_record()]
        snapshot = [dict(row) for row in records]
        filter_by_league(records, "GT")
        self.assertEqual(records, snapshot)

    def test_modifying_result_does_not_modify_original(self):
        original = make_record()
        result = player_history([original], "David")
        result[0]["player"] = "Changed"
        self.assertEqual(original["player"], "David")

    def test_load_and_queries_do_not_write_the_source(self):
        with temporary_folder() as folder:
            path = folder / "history.jsonl"
            write_jsonl(path, [make_record()])
            before = path.read_bytes()
            records = load_history(path)
            latest_matches(records, 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([item.name for item in folder.iterdir()], ["history.jsonl"])


if __name__ == "__main__":
    unittest.main()
