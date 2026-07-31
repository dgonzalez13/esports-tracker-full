import json
from contextlib import contextmanager
from pathlib import Path
import unittest
import uuid

from match_history import name_key
from temporal_analysis import (
    RecentHistoryComparison,
    TemporalWindowStats,
    calculate_all_player_windows,
    calculate_all_recent_forms,
    calculate_player_windows,
    calculate_recent_form,
    calculate_recent_vs_rival,
    calculate_temporal_window,
    calculate_temporal_windows,
    compare_recent_to_history,
    empty_temporal_window,
    load_recent_forms,
    load_temporal_windows,
)


TEST_TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def temporary_folder():
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield path


def match(
    index,
    result,
    player="David",
    rival="Fox",
    league="GT",
):
    prefix = league.casefold()
    return {
        "league": league,
        "player": player,
        "player_key": name_key(player),
        "rival": rival,
        "rival_key": name_key(rival),
        "result": result,
        "timestamp_utc": f"2026-07-{index:02d}T08:00:00Z",
        "timestamp": f"2026-07-{index:02d}T08:00:00+00:00",
        "match_id": f"{prefix}:{index}",
        "perspective_id": f"{prefix}:{index}:{name_key(player)}",
    }


def write_jsonl(path, records):
    Path(path).write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class RecentFormTests(unittest.TestCase):
    def test_temporal_model_has_exact_required_keys(self):
        expected = {
            "league", "player", "window", "available", "wins", "draws",
            "losses", "win_pct", "draw_pct", "loss_pct", "sequence",
            "current_streak_result", "current_streak", "first_match_date",
            "last_match_date",
        }
        self.assertEqual(TemporalWindowStats.__required_keys__, frozenset(expected))
        self.assertEqual(TemporalWindowStats.__optional_keys__, frozenset())

    def test_comparison_model_has_exact_required_keys(self):
        expected = {
            "league", "player", "window", "recent_available",
            "historical_played", "recent_win_pct", "historical_win_pct",
            "win_pct_delta", "recent_draw_pct", "historical_draw_pct",
            "draw_pct_delta", "recent_loss_pct", "historical_loss_pct",
            "loss_pct_delta",
        }
        self.assertEqual(RecentHistoryComparison.__required_keys__, frozenset(expected))
        self.assertEqual(RecentHistoryComparison.__optional_keys__, frozenset())

    def test_empty_temporal_window_exact_values(self):
        stats = empty_temporal_window(" David ", 5, "gt")
        self.assertEqual(
            stats,
            {
                "league": "GT", "player": "David", "window": 5,
                "available": 0, "wins": 0, "draws": 0, "losses": 0,
                "win_pct": 0.0, "draw_pct": 0.0, "loss_pct": 0.0,
                "sequence": "", "current_streak_result": None,
                "current_streak": 0, "first_match_date": None,
                "last_match_date": None,
            },
        )

    def test_canonical_window_sequence_is_chronological(self):
        records = [match(i, result) for i, result in enumerate("VEDVE", 1)]
        stats = calculate_temporal_window(reversed(records), "David", 3)
        self.assertEqual(stats["sequence"], "DVE")

    def test_window_is_applied_after_invalid_results_are_removed(self):
        records = [match(i, result) for i, result in enumerate(("V", "X", "E", "D", "V"), 1)]
        stats = calculate_temporal_window(records, "David", 3)
        self.assertEqual(stats["sequence"], "EDV")
        self.assertEqual(stats["available"], 3)

    def test_canonical_incomplete_window_and_percentages(self):
        records = [match(1, "V"), match(2, "E"), match(3, "D")]
        stats = calculate_temporal_window(records, "David", 5)
        self.assertEqual(stats["available"], 3)
        self.assertEqual(
            (stats["win_pct"], stats["draw_pct"], stats["loss_pct"]),
            (33.33, 33.33, 33.33),
        )

    def test_canonical_current_streak(self):
        records = [match(i, result) for i, result in enumerate("VEDDD", 1)]
        stats = calculate_temporal_window(records, "David", 4)
        self.assertEqual(stats["sequence"], "EDDD")
        self.assertEqual(stats["current_streak_result"], "D")
        self.assertEqual(stats["current_streak"], 3)

    def test_last_n_uses_only_latest_perspectives(self):
        records = [match(i, result) for i, result in enumerate("DDDVV", 1)]
        stats = calculate_recent_form(records, "David", 2, league="GT")
        self.assertEqual(stats["played"], 2)
        self.assertEqual(stats["wins"], 2)
        self.assertEqual(stats["first_match_date"], "2026-07-04")
        self.assertEqual(stats["last_match_date"], "2026-07-05")

    def test_window_retains_all_historical_comparison_fields(self):
        records = [match(i, result) for i, result in enumerate("DDDVV", 1)]
        stats = calculate_recent_form(records, "David", 2)
        self.assertEqual(stats["historical_played"], 5)
        self.assertEqual(stats["historical_win_pct"], 40.0)
        self.assertEqual(stats["win_pct_delta"], 60.0)

    def test_incomplete_window_is_explicit(self):
        stats = calculate_recent_form([match(1, "V"), match(2, "E")], "David", 5)
        self.assertEqual(stats["available_matches"], 2)
        self.assertFalse(stats["window_complete"])

    def test_complete_window_is_explicit(self):
        records = [match(i, "V") for i in range(1, 6)]
        stats = calculate_recent_form(records, "David", 5)
        self.assertTrue(stats["window_complete"])

    def test_empty_player_has_no_trend(self):
        stats = calculate_recent_form([], "Nobody", 5, league="GT")
        self.assertEqual(stats["played"], 0)
        self.assertIsNone(stats["trend"])
        self.assertEqual(stats["win_pct_delta"], 0.0)

    def test_up_trend(self):
        records = [match(i, result) for i, result in enumerate("DDDDDVVVVV", 1)]
        stats = calculate_recent_form(records, "David", 5)
        self.assertEqual(stats["trend"], "UP")
        self.assertEqual(stats["win_pct_delta"], 50.0)

    def test_down_trend(self):
        records = [match(i, result) for i, result in enumerate("VVVVVDDDDD", 1)]
        stats = calculate_recent_form(records, "David", 5)
        self.assertEqual(stats["trend"], "DOWN")
        self.assertEqual(stats["win_pct_delta"], -50.0)

    def test_stable_trend(self):
        records = [match(i, "V") for i in range(1, 11)]
        stats = calculate_recent_form(records, "David", 5)
        self.assertEqual(stats["trend"], "STABLE")
        self.assertEqual(stats["win_pct_delta"], 0.0)

    def test_threshold_is_configurable(self):
        records = [match(i, result) for i, result in enumerate("DDDDDVVVVV", 1)]
        stats = calculate_recent_form(records, "David", 5, trend_threshold=60)
        self.assertEqual(stats["trend"], "STABLE")

    def test_zero_delta_is_stable_even_with_zero_threshold(self):
        records = [match(i, "V") for i in range(1, 6)]
        stats = calculate_recent_form(records, "David", 5, trend_threshold=0)
        self.assertEqual(stats["trend"], "STABLE")

    def test_input_order_does_not_affect_window(self):
        records = [match(i, result) for i, result in enumerate("DDDVV", 1)]
        stats = calculate_recent_form(reversed(records), "David", 2)
        self.assertEqual(stats["wins"], 2)

    def test_other_players_are_excluded_before_window(self):
        records = [match(1, "D"), match(2, "V", player="Fox"), match(3, "V")]
        stats = calculate_recent_form(records, "David", 1)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["historical_played"], 2)

    def test_league_filter_is_applied_before_window(self):
        records = [match(1, "D", league="GT"), match(2, "V", league="EADRIATIC")]
        stats = calculate_recent_form(records, "David", 1, league="GT")
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["league"], "GT")

    def test_source_records_are_not_modified(self):
        records = [match(1, "D"), match(2, "V")]
        snapshot = [dict(record) for record in records]
        calculate_recent_form(records, "David", 1)
        self.assertEqual(records, snapshot)


class HeadToHeadWindowTests(unittest.TestCase):
    def test_directional_h2h_excludes_reverse_perspective(self):
        records = [
            match(1, "V", player="David", rival="Fox"),
            match(1, "D", player="Fox", rival="David"),
        ]
        stats = calculate_recent_vs_rival(records, "David", "Fox", 5)
        self.assertEqual(stats["played"], 1)
        self.assertEqual(stats["wins"], 1)

    def test_h2h_excludes_other_rivals(self):
        records = [
            match(1, "D", rival="Wolf"),
            match(2, "V", rival="Fox"),
        ]
        stats = calculate_recent_vs_rival(records, "David", "Fox", 5)
        self.assertEqual(stats["played"], 1)
        self.assertEqual(stats["wins"], 1)

    def test_h2h_takes_latest_n_against_that_rival(self):
        records = [match(i, result, rival="Fox") for i, result in enumerate("DDVV", 1)]
        stats = calculate_recent_vs_rival(records, "David", "Fox", 2)
        self.assertEqual(stats["wins"], 2)


class MultipleWindowsAndValidationTests(unittest.TestCase):
    def test_canonical_windows_are_deduplicated_and_sorted(self):
        records = [match(i, "V") for i in range(1, 11)]
        rows = calculate_player_windows(
            records, "David", windows=(value for value in (10, 5, 10, 20))
        )
        self.assertEqual([row["window"] for row in rows], [5, 10, 20])

    def test_canonical_empty_windows_returns_empty_list(self):
        self.assertEqual(calculate_player_windows([], "David", windows=[]), [])

    def test_default_last_five_and_last_ten(self):
        records = [match(i, "V") for i in range(1, 11)]
        rows = calculate_temporal_windows(records, "David")
        self.assertEqual([row["window_size"] for row in rows], [5, 10])

    def test_requested_window_order_is_preserved(self):
        records = [match(i, "V") for i in range(1, 11)]
        rows = calculate_temporal_windows(records, "David", windows=(10, 3, 5))
        self.assertEqual([row["window_size"] for row in rows], [10, 3, 5])

    def test_empty_window_collection_returns_empty_list(self):
        self.assertEqual(calculate_temporal_windows([], "David", windows=[]), [])

    def test_invalid_window_is_rejected(self):
        for value in (0, -1, True, 2.5, "5", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_recent_form([], "David", value)

    def test_invalid_threshold_is_rejected(self):
        for value in (-1, True, "5", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_recent_form([], "David", 5, trend_threshold=value)

    def test_invalid_window_inside_collection_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_temporal_windows([], "David", windows=(5, 0))


class AggregateAndLoadTests(unittest.TestCase):
    def test_canonical_all_windows_sort_by_league_player_window(self):
        records = [
            match(1, "V", player="Zed", league="GT"),
            match(2, "D", player="David", league="EADRIATIC"),
            match(3, "E", player="David", league="GT"),
        ]
        rows = calculate_all_player_windows(records, windows=(10, 5))
        self.assertEqual(
            [(row["league"], row["player"], row["window"]) for row in rows],
            [
                ("EADRIATIC", "David", 5), ("EADRIATIC", "David", 10),
                ("GT", "David", 5), ("GT", "David", 10),
                ("GT", "Zed", 5), ("GT", "Zed", 10),
            ],
        )

    def test_recent_history_comparison_includes_wed_deltas(self):
        records = [match(i, result) for i, result in enumerate("VVEDD", 1)]
        result = compare_recent_to_history(records, "David", 2, league="GT")
        self.assertEqual(result["recent_available"], 2)
        self.assertEqual(result["historical_played"], 5)
        self.assertEqual((result["recent_win_pct"], result["historical_win_pct"]), (0.0, 40.0))
        self.assertEqual((result["win_pct_delta"], result["draw_pct_delta"], result["loss_pct_delta"]), (-40.0, -20.0, 60.0))

    def test_canonical_loader_combines_and_separates_leagues(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            ead_path = folder / "ead.jsonl"
            write_jsonl(gt_path, [match(1, "V", league="GT")])
            write_jsonl(ead_path, [match(2, "D", player="David", league="EADRIATIC")])
            rows = load_temporal_windows(gt_path, ead_path, windows=(5,))
        self.assertEqual(
            {(row["league"], row["player"]) for row in rows},
            {("GT", "David"), ("EADRIATIC", "David")},
        )

    def test_canonical_queries_do_not_modify_input(self):
        records = [match(1, "V"), match(2, "D")]
        snapshot = [dict(record) for record in records]
        calculate_temporal_window(records, "David", 1)
        compare_recent_to_history(records, "David", 1)
        self.assertEqual(records, snapshot)

    def test_all_players_and_leagues_remain_independent(self):
        records = [
            match(1, "V", player="David", league="GT"),
            match(2, "D", player="David", league="EADRIATIC"),
            match(3, "E", player="Fox", league="GT"),
        ]
        rows = calculate_all_recent_forms(records, 5)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {(row["league"], row["player"]) for row in rows},
            {("GT", "David"), ("EADRIATIC", "David"), ("GT", "Fox")},
        )

    def test_all_players_can_be_filtered_by_league(self):
        records = [
            match(1, "V", league="GT"),
            match(2, "D", league="EADRIATIC"),
        ]
        rows = calculate_all_recent_forms(records, 5, league="GT")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["league"], "GT")

    def test_loader_combines_both_histories_through_query_api(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            ead_path = folder / "ead.jsonl"
            write_jsonl(gt_path, [match(1, "V", league="GT")])
            write_jsonl(ead_path, [match(2, "D", player="Eric", league="EADRIATIC")])
            rows = load_recent_forms(5, gt_path, ead_path)
        self.assertEqual({row["league"] for row in rows}, {"GT", "EADRIATIC"})


if __name__ == "__main__":
    unittest.main()
