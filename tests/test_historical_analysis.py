import json
from contextlib import contextmanager
from pathlib import Path
import unittest
import uuid

from historical_analysis import (
    PlayerHistoricalStats,
    calculate_historical_stats,
    calculate_player_stats,
    empty_player_stats,
    load_historical_stats,
)
from match_history import name_key


TEST_TEMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def temporary_folder():
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield path


def match(index, result, player="David", league="GT", hour=None):
    hour = index if hour is None else hour
    prefix = league.casefold()
    return {
        "league": league,
        "player": player,
        "player_key": name_key(player),
        "rival": "Fox",
        "rival_key": "fox",
        "result": result,
        "timestamp_utc": f"2026-07-{index:02d}T{hour:02d}:00:00Z",
        "timestamp": f"2026-07-{index:02d}T{hour:02d}:00:00+00:00",
        "match_id": f"{prefix}:{index}",
        "perspective_id": f"{prefix}:{index}:{name_key(player)}",
    }


def write_jsonl(path, records):
    Path(path).write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class PlayerStatisticsTests(unittest.TestCase):
    def test_typed_model_defines_the_exact_public_shape(self):
        expected = {
            "league", "player", "played", "wins", "draws", "losses",
            "win_pct", "draw_pct", "loss_pct", "current_streak_result",
            "current_streak", "best_win_streak", "best_loss_streak",
            "first_match_date", "last_match_date",
        }
        self.assertEqual(PlayerHistoricalStats.__required_keys__, frozenset(expected))
        self.assertEqual(PlayerHistoricalStats.__optional_keys__, frozenset())

    def test_empty_and_calculated_results_share_the_model_shape(self):
        empty = empty_player_stats("David", "GT")
        calculated = calculate_player_stats([match(1, "V")], "David", "GT")
        self.assertEqual(set(empty), set(calculated))
        self.assertIsInstance(empty, dict)
        self.assertIsInstance(calculated, dict)

    def test_calculates_complete_statistics(self):
        records = [match(1, "V"), match(2, "E"), match(3, "D"), match(4, "V")]
        stats = calculate_player_stats(records, "David", league="GT")
        self.assertEqual(stats["played"], 4)
        self.assertEqual((stats["wins"], stats["draws"], stats["losses"]), (2, 1, 1))
        self.assertEqual((stats["win_pct"], stats["draw_pct"], stats["loss_pct"]), (50.0, 25.0, 25.0))
        self.assertEqual(stats["first_match_date"], "2026-07-01")
        self.assertEqual(stats["last_match_date"], "2026-07-04")

    def test_player_without_matches_has_stable_zero_values(self):
        stats = calculate_player_stats([], "Nobody", league="GT")
        self.assertEqual(stats, empty_player_stats("Nobody", "GT"))
        self.assertEqual(stats["current_streak"], 0)
        self.assertIsNone(stats["current_streak_result"])

    def test_only_wins(self):
        stats = calculate_player_stats([match(1, "V"), match(2, "V")], "David")
        self.assertEqual(stats["win_pct"], 100.0)
        self.assertEqual(stats["best_win_streak"], 2)
        self.assertEqual(stats["best_loss_streak"], 0)

    def test_only_losses(self):
        stats = calculate_player_stats([match(1, "D"), match(2, "D")], "David")
        self.assertEqual(stats["loss_pct"], 100.0)
        self.assertEqual(stats["best_loss_streak"], 2)
        self.assertEqual(stats["best_win_streak"], 0)

    def test_draws_are_counted_and_can_be_current_streak(self):
        stats = calculate_player_stats([match(1, "V"), match(2, "E"), match(3, "E")], "David")
        self.assertEqual(stats["draws"], 2)
        self.assertEqual(stats["draw_pct"], 66.67)
        self.assertEqual(stats["current_streak_result"], "E")
        self.assertEqual(stats["current_streak"], 2)

    def test_current_and_best_streaks(self):
        sequence = "VVVEDDDVVDD"
        stats = calculate_player_stats(
            [match(index, result) for index, result in enumerate(sequence, 1)], "David"
        )
        self.assertEqual(stats["current_streak_result"], "D")
        self.assertEqual(stats["current_streak"], 2)
        self.assertEqual(stats["best_win_streak"], 3)
        self.assertEqual(stats["best_loss_streak"], 3)

    def test_input_order_does_not_change_chronological_streaks(self):
        chronological = [match(1, "V"), match(2, "D"), match(3, "D")]
        stats = calculate_player_stats(reversed(chronological), "David")
        self.assertEqual(stats["current_streak_result"], "D")
        self.assertEqual(stats["current_streak"], 2)

    def test_other_players_and_rival_perspectives_are_excluded(self):
        records = [match(1, "V"), match(2, "D", player="Fox")]
        stats = calculate_player_stats(records, "David")
        self.assertEqual(stats["played"], 1)
        self.assertEqual(stats["wins"], 1)

    def test_invalid_results_are_not_counted(self):
        records = [match(1, "V"), match(2, "X")]
        stats = calculate_player_stats(records, "David")
        self.assertEqual(stats["played"], 1)

    def test_missing_dates_do_not_prevent_totals(self):
        record = match(1, "V")
        record.pop("timestamp_utc")
        record.pop("timestamp")
        stats = calculate_player_stats([record], "David")
        self.assertEqual(stats["played"], 1)
        self.assertIsNone(stats["first_match_date"])
        self.assertIsNone(stats["last_match_date"])


class AggregateStatisticsTests(unittest.TestCase):
    def test_leagues_are_independent_for_same_player_name(self):
        records = [match(1, "V", league="GT"), match(2, "D", league="EADRIATIC")]
        rows = calculate_historical_stats(records)
        self.assertEqual(len(rows), 2)
        by_league = {row["league"]: row for row in rows}
        self.assertEqual(by_league["GT"]["wins"], 1)
        self.assertEqual(by_league["EADRIATIC"]["losses"], 1)

    def test_optional_league_filter(self):
        records = [match(1, "V", league="GT"), match(2, "D", league="EADRIATIC")]
        rows = calculate_historical_stats(records, league="gt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["league"], "GT")

    def test_multiple_players_are_sorted_deterministically(self):
        records = [match(1, "V", player="Zed"), match(2, "D", player="Álex")]
        rows = calculate_historical_stats(records)
        self.assertEqual([row["player"] for row in rows], ["Zed", "Álex"])

    def test_combined_gt_and_eadriatic_files_are_loaded_through_query_api(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            ead_path = folder / "ead.jsonl"
            write_jsonl(gt_path, [match(1, "V", league="GT")])
            write_jsonl(ead_path, [match(2, "E", player="Eric", league="EADRIATIC")])
            rows = load_historical_stats(gt_path, ead_path)
        self.assertEqual({row["league"] for row in rows}, {"GT", "EADRIATIC"})
        self.assertEqual(sum(row["played"] for row in rows), 2)

    def test_missing_history_file_is_allowed(self):
        with temporary_folder() as folder:
            gt_path = folder / "gt.jsonl"
            write_jsonl(gt_path, [match(1, "V")])
            rows = load_historical_stats(gt_path, folder / "missing.jsonl")
        self.assertEqual(len(rows), 1)

    def test_empty_records_return_empty_rows(self):
        self.assertEqual(calculate_historical_stats([]), [])


if __name__ == "__main__":
    unittest.main()
