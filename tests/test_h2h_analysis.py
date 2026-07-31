import json
from contextlib import contextmanager
from pathlib import Path
import unittest
import uuid

from h2h_analysis import (
    DEFAULT_H2H_WINDOW,
    H2HComparison,
    H2HRecentStats,
    H2HStats,
    calculate_all_h2h,
    calculate_h2h_stats,
    calculate_recent_h2h,
    compare_recent_h2h_to_history,
    empty_h2h_stats,
    load_all_h2h,
)
from match_history import name_key


TEST_TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def temporary_folder():
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield path


def perspective(
    index,
    result,
    player="David",
    rival="Fox",
    league="GT",
    timestamp=None,
    match_id=None,
):
    timestamp = timestamp or f"2026-07-{index:02d}T08:00:00Z"
    match_id = match_id or f"{league.casefold()}:{index:02d}"
    return {
        "league": league,
        "player": player,
        "player_key": name_key(player),
        "rival": rival,
        "rival_key": name_key(rival),
        "result": result,
        "timestamp_utc": timestamp,
        "timestamp": timestamp,
        "match_id": match_id,
        "perspective_id": f"{match_id}:{name_key(player)}",
    }


def write_jsonl(path, records):
    Path(path).write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class ModelAndEmptyTests(unittest.TestCase):
    def test_historical_model_has_exact_keys(self):
        expected = {
            "league", "player", "rival", "played", "wins", "draws",
            "losses", "win_pct", "draw_pct", "loss_pct", "sequence",
            "first_match_date", "last_match_date",
        }
        self.assertEqual(H2HStats.__required_keys__, frozenset(expected))
        self.assertEqual(H2HStats.__optional_keys__, frozenset())

    def test_recent_model_has_exact_keys(self):
        expected = {
            "league", "player", "rival", "window", "available",
            "window_complete", "wins", "draws", "losses", "win_pct",
            "draw_pct", "loss_pct", "sequence", "current_streak_result",
            "current_streak", "first_match_date", "last_match_date",
        }
        self.assertEqual(H2HRecentStats.__required_keys__, frozenset(expected))
        self.assertEqual(H2HRecentStats.__optional_keys__, frozenset())

    def test_comparison_model_has_exact_keys(self):
        expected = {
            "league", "player", "rival", "window", "recent_available",
            "historical_played", "historical_win_pct", "recent_win_pct",
            "win_pct_delta", "historical_draw_pct", "recent_draw_pct",
            "draw_pct_delta", "historical_loss_pct", "recent_loss_pct",
            "loss_pct_delta", "trend", "sample_status",
        }
        self.assertEqual(H2HComparison.__required_keys__, frozenset(expected))
        self.assertEqual(H2HComparison.__optional_keys__, frozenset())

    def test_outputs_are_dictionaries(self):
        self.assertIsInstance(empty_h2h_stats("David", "Fox"), dict)
        self.assertIsInstance(calculate_recent_h2h([], "David", "Fox"), dict)
        self.assertIsInstance(compare_recent_h2h_to_history([], "David", "Fox"), dict)

    def test_empty_h2h_has_exact_zero_values(self):
        result = empty_h2h_stats(" David ", " Fox ", " gt ")
        self.assertEqual(result["league"], "GT")
        self.assertEqual((result["player"], result["rival"]), ("David", "Fox"))
        self.assertEqual((result["played"], result["wins"], result["draws"], result["losses"]), (0, 0, 0, 0))
        self.assertEqual((result["win_pct"], result["draw_pct"], result["loss_pct"]), (0.0, 0.0, 0.0))
        self.assertEqual(result["sequence"], "")
        self.assertIsNone(result["first_match_date"])
        self.assertIsNone(result["last_match_date"])

    def test_missing_player_or_rival_returns_empty(self):
        records = [perspective(1, "V")]
        self.assertEqual(calculate_h2h_stats(records, "Nobody", "Fox")["played"], 0)
        self.assertEqual(calculate_h2h_stats(records, "David", "Nobody")["played"], 0)


class HistoricalDirectionalTests(unittest.TestCase):
    def test_exact_counts_percentages_sequence_and_dates(self):
        records = [perspective(i, result) for i, result in enumerate("VEDV", 1)]
        result = calculate_h2h_stats(records, "David", "Fox", "GT")
        self.assertEqual(result["played"], 4)
        self.assertEqual((result["wins"], result["draws"], result["losses"]), (2, 1, 1))
        self.assertEqual((result["win_pct"], result["draw_pct"], result["loss_pct"]), (50.0, 25.0, 25.0))
        self.assertEqual(result["sequence"], "VEDV")
        self.assertEqual((result["first_match_date"], result["last_match_date"]), ("2026-07-01", "2026-07-04"))

    def test_inverse_perspective_is_not_included(self):
        records = [
            perspective(1, "V", "David", "Fox"),
            perspective(1, "D", "Fox", "David"),
        ]
        david = calculate_h2h_stats(records, "David", "Fox")
        fox = calculate_h2h_stats(records, "Fox", "David")
        self.assertEqual((david["sequence"], fox["sequence"]), ("V", "D"))

    def test_other_rivals_are_excluded(self):
        records = [perspective(1, "D", rival="Wolf"), perspective(2, "V", rival="Fox")]
        self.assertEqual(calculate_h2h_stats(records, "David", "Fox")["sequence"], "V")

    def test_leagues_are_separate_and_filter_is_normalized(self):
        records = [
            perspective(1, "V", league="GT"),
            perspective(2, "D", league="EADRIATIC"),
        ]
        gt = calculate_h2h_stats(records, "David", "Fox", " gt ")
        ead = calculate_h2h_stats(records, "David", "Fox", "eadriatic")
        self.assertEqual((gt["sequence"], ead["sequence"]), ("V", "D"))

    def test_reversed_input_is_sorted_chronologically(self):
        records = [perspective(i, result) for i, result in enumerate("VEDV", 1)]
        self.assertEqual(calculate_h2h_stats(reversed(records), "David", "Fox")["sequence"], "VEDV")

    def test_equal_timestamps_use_deterministic_identifiers(self):
        timestamp = "2026-07-01T08:00:00Z"
        records = [
            perspective(1, "D", timestamp=timestamp, match_id="gt:b"),
            perspective(1, "V", timestamp=timestamp, match_id="gt:a"),
        ]
        self.assertEqual(calculate_h2h_stats(records, "David", "Fox")["sequence"], "VD")

    def test_invalid_results_are_ignored_without_error(self):
        values = ("V", "X", None, "", 3, "D")
        records = [perspective(i, result) for i, result in enumerate(values, 1)]
        result = calculate_h2h_stats(records, "David", "Fox")
        self.assertEqual((result["played"], result["sequence"]), (2, "VD"))

    def test_missing_or_invalid_dates_still_count(self):
        missing = perspective(1, "V")
        missing.pop("timestamp_utc")
        missing.pop("timestamp")
        invalid = perspective(2, "D", timestamp="bad")
        result = calculate_h2h_stats([missing, invalid], "David", "Fox")
        self.assertEqual(result["played"], 2)
        self.assertIsNone(result["first_match_date"])
        self.assertIsNone(result["last_match_date"])


class RecentH2HTests(unittest.TestCase):
    def test_default_window_is_last_twenty(self):
        result = calculate_recent_h2h([], "David", "Fox")
        self.assertEqual(result["window"], DEFAULT_H2H_WINDOW)

    def test_custom_window_takes_latest_results_ascending(self):
        records = [perspective(i, result) for i, result in enumerate("VEDVE", 1)]
        result = calculate_recent_h2h(records, "David", "Fox", 3)
        self.assertEqual(result["sequence"], "DVE")

    def test_invalid_results_are_removed_before_window(self):
        values = ("V", "X", "E", None, "D", "V")
        records = [perspective(i, result) for i, result in enumerate(values, 1)]
        self.assertEqual(calculate_recent_h2h(records, "David", "Fox", 3)["sequence"], "EDV")

    def test_incomplete_and_complete_windows(self):
        records = [perspective(1, "V"), perspective(2, "E")]
        low = calculate_recent_h2h(records, "David", "Fox", 3)
        complete = calculate_recent_h2h(records, "David", "Fox", 2)
        self.assertFalse(low["window_complete"])
        self.assertTrue(complete["window_complete"])

    def test_recent_counts_percentages_and_dates(self):
        records = [perspective(i, result) for i, result in enumerate("VVED", 1)]
        result = calculate_recent_h2h(records, "David", "Fox", 3)
        self.assertEqual((result["available"], result["wins"], result["draws"], result["losses"]), (3, 1, 1, 1))
        self.assertEqual((result["win_pct"], result["draw_pct"], result["loss_pct"]), (33.33, 33.33, 33.33))
        self.assertEqual((result["first_match_date"], result["last_match_date"]), ("2026-07-02", "2026-07-04"))

    def test_current_streak(self):
        records = [perspective(i, result) for i, result in enumerate("VEDDD", 1)]
        result = calculate_recent_h2h(records, "David", "Fox", 4)
        self.assertEqual((result["current_streak_result"], result["current_streak"]), ("D", 3))


class ComparisonTests(unittest.TestCase):
    def test_positive_negative_and_zero_deltas(self):
        up_records = [perspective(i, r) for i, r in enumerate("DDDDDVVVVV", 1)]
        down_records = [perspective(i, r) for i, r in enumerate("VVVVVDDDDD", 1)]
        flat_records = [perspective(i, "V") for i in range(1, 11)]
        up = compare_recent_h2h_to_history(up_records, "David", "Fox", 5)
        down = compare_recent_h2h_to_history(down_records, "David", "Fox", 5)
        flat = compare_recent_h2h_to_history(flat_records, "David", "Fox", 5)
        self.assertEqual((up["win_pct_delta"], up["trend"]), (50.0, "UP"))
        self.assertEqual((down["win_pct_delta"], down["trend"]), (-50.0, "DOWN"))
        self.assertEqual((flat["win_pct_delta"], flat["trend"]), (0.0, "STABLE"))

    def test_empty_recent_has_no_trend(self):
        result = compare_recent_h2h_to_history([], "David", "Fox")
        self.assertIsNone(result["trend"])

    def test_threshold_is_configurable(self):
        records = [perspective(i, r) for i, r in enumerate("DDDDDVVVVV", 1)]
        result = compare_recent_h2h_to_history(records, "David", "Fox", 5, trend_threshold=60)
        self.assertEqual(result["trend"], "STABLE")

    def test_zero_threshold_and_zero_delta_is_stable(self):
        records = [perspective(i, "V") for i in range(1, 6)]
        result = compare_recent_h2h_to_history(records, "David", "Fox", 5, trend_threshold=0)
        self.assertEqual(result["trend"], "STABLE")

    def test_wed_deltas_are_exact_and_rounded(self):
        records = [perspective(i, r) for i, r in enumerate("VVEDD", 1)]
        result = compare_recent_h2h_to_history(records, "David", "Fox", 2)
        self.assertEqual((result["win_pct_delta"], result["draw_pct_delta"], result["loss_pct_delta"]), (-40.0, -20.0, 60.0))

    def test_sample_status_empty_low_and_complete(self):
        empty = compare_recent_h2h_to_history([], "David", "Fox", 3)
        records = [perspective(1, "V"), perspective(2, "D")]
        low = compare_recent_h2h_to_history(records, "David", "Fox", 3)
        complete = compare_recent_h2h_to_history(records, "David", "Fox", 2)
        self.assertEqual((empty["sample_status"], low["sample_status"], complete["sample_status"]), ("EMPTY", "LOW_SAMPLE", "COMPLETE"))


class AllRelationsTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            perspective(1, "V", "David", "Fox", "GT"),
            perspective(1, "D", "Fox", "David", "GT"),
            perspective(2, "E", "David", "Wolf", "GT"),
            perspective(3, "D", "David", "Fox", "EADRIATIC"),
        ]

    def test_all_directional_relations_and_leagues(self):
        rows = calculate_all_h2h(self.records, window=2)
        self.assertEqual(
            {(r["league"], r["player"], r["rival"]) for r in rows},
            {
                ("GT", "David", "Fox"), ("GT", "Fox", "David"),
                ("GT", "David", "Wolf"), ("EADRIATIC", "David", "Fox"),
            },
        )

    def test_deterministic_league_player_rival_order(self):
        rows = calculate_all_h2h(reversed(self.records), window=2)
        identities = [(r["league"], r["player"], r["rival"]) for r in rows]
        self.assertEqual(
            identities,
            [
                ("EADRIATIC", "David", "Fox"), ("GT", "David", "Fox"),
                ("GT", "David", "Wolf"), ("GT", "Fox", "David"),
            ],
        )

    def test_league_filter(self):
        rows = calculate_all_h2h(self.records, league=" gt ")
        self.assertTrue(rows)
        self.assertEqual({row["league"] for row in rows}, {"GT"})

    def test_minimum_historical_filter(self):
        records = [*self.records, perspective(4, "V", "David", "Fox", "GT")]
        rows = calculate_all_h2h(records, min_historical_matches=2)
        self.assertEqual([(row["league"], row["player"], row["rival"]) for row in rows], [("GT", "David", "Fox")])

    def test_incomplete_identity_records_are_ignored(self):
        broken = [
            {}, {"league": "GT", "player": "David"},
            {"league": "GT", "player": "", "player_key": "", "rival": "Fox", "rival_key": "fox"},
        ]
        self.assertEqual(calculate_all_h2h(broken), [])


class ValidationImmutabilityAndLoadTests(unittest.TestCase):
    def test_invalid_windows_are_rejected(self):
        for value in (0, -1, 1.5, "20", None, True, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_recent_h2h([], "David", "Fox", value)

    def test_invalid_thresholds_are_rejected(self):
        for value in (-1, "5", None, True, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare_recent_h2h_to_history([], "David", "Fox", trend_threshold=value)

    def test_invalid_minimums_are_rejected(self):
        for value in (0, -1, 1.5, "1", None, True, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_all_h2h([], min_historical_matches=value)

    def test_invalid_names_are_rejected(self):
        calls = (
            lambda: empty_h2h_stats("", "Fox"),
            lambda: calculate_h2h_stats([], "David", " "),
            lambda: calculate_recent_h2h([], None, "Fox"),
            lambda: compare_recent_h2h_to_history([], "David", 2),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_input_and_order_are_not_modified(self):
        records = [perspective(2, "D"), perspective(1, "V")]
        snapshot = [dict(record) for record in records]
        calculate_h2h_stats(records, "David", "Fox")
        compare_recent_h2h_to_history(records, "David", "Fox")
        self.assertEqual(records, snapshot)

    def test_modifying_output_does_not_change_input(self):
        record = perspective(1, "V")
        result = calculate_h2h_stats([record], "David", "Fox")
        result["sequence"] = "D"
        self.assertEqual(record["result"], "V")

    def test_loader_combines_gt_and_eadriatic(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            ead_path = folder / "ead.jsonl"
            write_jsonl(gt_path, [perspective(1, "V", league="GT")])
            write_jsonl(ead_path, [perspective(2, "D", league="EADRIATIC")])
            rows = load_all_h2h(gt_path, ead_path)
        self.assertEqual({row["league"] for row in rows}, {"GT", "EADRIATIC"})

    def test_loader_allows_one_or_both_missing_files(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            write_jsonl(gt_path, [perspective(1, "V")])
            one = load_all_h2h(gt_path, folder / "missing.jsonl")
            none = load_all_h2h(folder / "missing-a", folder / "missing-b")
        self.assertEqual(len(one), 1)
        self.assertEqual(none, [])

    def test_queries_do_not_write_source_files(self):
        with temporary_folder() as folder:
            path = folder / "gt.jsonl"
            write_jsonl(path, [perspective(1, "V")])
            before = path.read_bytes()
            load_all_h2h(path, folder / "missing")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([item.name for item in folder.iterdir()], ["gt.jsonl"])


if __name__ == "__main__":
    unittest.main()
