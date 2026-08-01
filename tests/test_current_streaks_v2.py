import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import current_streaks_v2 as v2
from match_history import name_key


def match(player="Lucas", league="GT", result="V", timestamp="2026-08-01T08:00:00Z", index=1, rival="Fox"):
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "rival": rival, "rival_key": name_key(rival), "result": result,
        "timestamp_utc": timestamp, "match_id": f"{league}:{player}:{index}",
        "perspective_id": f"{league}:{player}:{index}:{name_key(player)}",
    }


def tracked(player="Lucas", league="GT", selected=False):
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "tracked": True, "selected": selected,
    }


class ModelsAndHistoryTests(unittest.TestCase):
    def test_models_have_exact_keys(self):
        expected = {
            "session_id", "league", "player", "player_key", "session_number",
            "start_timestamp", "end_timestamp", "start_local", "end_local",
            "duration_minutes", "played", "wins", "draws", "losses", "win_pct",
            "draw_pct", "loss_pct", "sequence", "last_10", "current_streak_result",
            "current_streak", "tracked", "balance", "active",
        }
        self.assertEqual(v2.PlayerSession.__required_keys__, frozenset(expected))
        self.assertEqual(v2.CurrentStreaksV2Payload.__required_keys__, frozenset({
            "generated_at", "session_gap_minutes", "active_window_minutes", "leagues",
        }))

    def test_history_filters_identity_invalid_data_and_sorts_without_mutation(self):
        records = [
            match(timestamp="2026-08-01T10:00:00Z", index=2),
            match(timestamp="2026-08-01T08:00:00Z", index=1),
            match(player="Fox", rival="Lucas", index=3),
            match(result="X", index=4), match(timestamp="broken", index=5),
            match(league="EADRIATIC", index=6),
        ]
        original = copy.deepcopy(records)
        rows = v2.player_session_history(records, "gt", "Lucas")
        self.assertEqual([row["match_id"] for row in rows], ["GT:Lucas:1", "GT:Lucas:2"])
        rows[0]["result"] = "D"
        self.assertEqual(records, original)

    def test_z_offset_and_naive_are_comparable(self):
        records = [
            match(timestamp="2026-08-01T12:00:00+02:00", index=1),
            match(timestamp="2026-08-01T10:01:00", index=2),
            match(timestamp="2026-08-01T10:02:00Z", index=3),
        ]
        self.assertEqual([r["match_id"] for r in v2.player_session_history(records, "GT", "Lucas")], ["GT:Lucas:1", "GT:Lucas:2", "GT:Lucas:3"])


class SessionSplittingTests(unittest.TestCase):
    def test_less_equal_and_greater_than_ninety(self):
        base = [
            match(timestamp="2026-08-01T08:00:00Z", index=1),
            match(timestamp="2026-08-01T09:29:00Z", index=2),
            match(timestamp="2026-08-01T10:59:00Z", index=3),
            match(timestamp="2026-08-01T12:30:00Z", index=4),
        ]
        sessions = v2.split_player_sessions(reversed(base))
        self.assertEqual([len(rows) for rows in sessions], [3, 1])

    def test_midnight_and_year_change_do_not_split(self):
        midnight = [
            match(timestamp="2026-08-01T20:00:00Z", index=1),
            match(timestamp="2026-08-01T21:30:00Z", index=2),
            match(timestamp="2026-08-01T22:15:00Z", index=3),
            match(timestamp="2026-08-01T23:00:00Z", index=4),
        ]
        year = [
            match(timestamp="2026-12-31T23:30:00Z", index=1),
            match(timestamp="2027-01-01T00:15:00Z", index=2),
        ]
        self.assertEqual(len(v2.split_player_sessions(midnight)), 1)
        self.assertEqual(len(v2.split_player_sessions(year)), 1)

    def test_two_and_three_sessions(self):
        times = ["08:00", "08:20", "08:40", "09:00", "15:00", "15:20", "15:40", "16:00", "20:00"]
        rows = [match(timestamp=f"2026-08-01T{time}:00Z", index=i) for i, time in enumerate(times, 1)]
        self.assertEqual([len(s) for s in v2.split_player_sessions(rows)], [4, 4, 1])

    def test_invalid_session_gap(self):
        for value in (0, -1, 1.5, True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                v2.split_player_sessions([], session_gap_minutes=value)


class SessionCalculationTests(unittest.TestCase):
    def calculate(self, sequence="VEDDD", end="2026-08-01T10:00:00Z", reference="2026-08-01T11:00:00Z", tracked_value=True):
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        rows = []
        for index, result in enumerate(sequence):
            stamp = end_dt - timedelta(minutes=(len(sequence) - 1 - index) * 10)
            rows.append(match(result=result, timestamp=stamp.isoformat().replace("+00:00", "Z"), index=index))
        return v2.calculate_player_session(
            rows, league="GT", player="Lucas", player_key="lucas", session_number=2,
            tracked=tracked_value,
            reference_time=datetime.fromisoformat(reference.replace("Z", "+00:00")),
        )

    def test_counts_percentages_duration_sequence_last10_and_id(self):
        session = self.calculate("VEDVVDD")
        self.assertEqual((session["wins"], session["draws"], session["losses"], session["played"]), (3, 1, 3, 7))
        self.assertEqual((session["win_pct"], session["draw_pct"], session["loss_pct"]), (42.86, 14.29, 42.86))
        self.assertEqual(session["sequence"], "VEDVVDD")
        self.assertEqual(session["last_10"], "VEDVVDD")
        self.assertEqual(session["duration_minutes"], 60)
        self.assertTrue(session["session_id"].startswith("gt:lucas:"))
        self.assertEqual(session["session_number"], 2)

    def test_single_match_and_last_ten(self):
        single = self.calculate("V")
        long = self.calculate("VE" * 6)
        self.assertEqual(single["duration_minutes"], 0)
        self.assertEqual(long["last_10"], ("VE" * 6)[-10:])

    def test_current_streak_v_e_d(self):
        for sequence, result, count in (("EDVVV", "V", 3), ("VDEE", "E", 2), ("VEDDD", "D", 3)):
            session = self.calculate(sequence)
            self.assertEqual((session["current_streak_result"], session["current_streak"]), (result, count))

    def test_balance_rules(self):
        self.assertEqual(self.calculate("VVDE")["balance"], "🟢")
        self.assertEqual(self.calculate("DDVE")["balance"], "🔴")
        self.assertEqual(self.calculate("VED")["balance"], "")
        self.assertEqual(self.calculate("VV", tracked_value=False)["balance"], "")

    def test_active_boundaries_and_future(self):
        exact = self.calculate("V", reference="2026-08-01T13:00:00Z")
        outside = self.calculate("V", reference="2026-08-01T13:00:01Z")
        future = self.calculate("V", reference="2026-08-01T09:59:00Z")
        self.assertTrue(exact["active"])
        self.assertFalse(outside["active"])
        self.assertFalse(future["active"])

    def test_cross_midnight_local_fields_and_duration(self):
        rows = [
            match(result="V", timestamp="2026-08-01T20:00:00Z", index=1),
            match(result="E", timestamp="2026-08-01T21:30:00Z", index=2),
            match(result="D", timestamp="2026-08-01T22:15:00Z", index=3),
            match(result="V", timestamp="2026-08-01T23:00:00Z", index=4),
        ]
        session = v2.calculate_player_session(rows, league="GT", player="Lucas", player_key="lucas", session_number=1, tracked=True, reference_time=datetime(2026, 8, 2, 0, tzinfo=timezone.utc))
        self.assertTrue(session["start_local"].startswith("2026-08-01T22:00"))
        self.assertTrue(session["end_local"].startswith("2026-08-02T01:00"))
        self.assertEqual((session["duration_minutes"], session["sequence"]), (180, "VEDV"))


class PayloadAndLoadingTests(unittest.TestCase):
    def test_latest_session_only_leagues_and_selected_tracked(self):
        records = [
            match(timestamp="2026-08-01T08:00:00Z", index=1),
            match(timestamp="2026-08-01T15:00:00Z", index=2),
            match(player="Lucas", league="EADRIATIC", timestamp="2026-08-01T16:00:00Z", index=3),
        ]
        payload = v2.calculate_current_streaks_v2(
            records, [tracked(selected=True), tracked(league="EADRIATIC")],
            reference_time=datetime(2026, 8, 1, 16, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(payload["leagues"]["GT"][0]["played"], 1)
        self.assertEqual(payload["leagues"]["GT"][0]["session_number"], 2)
        self.assertEqual(payload["leagues"]["EADRIATIC"][0]["league"], "EADRIATIC")

    def test_history_is_built_once_per_identity_and_input_immutable(self):
        records = [match()]
        original = copy.deepcopy(records)
        with patch.object(v2, "player_session_history", wraps=v2.player_session_history) as history:
            v2.calculate_current_streaks_v2(records, [tracked(), tracked()], reference_time=datetime.now(timezone.utc))
        self.assertEqual(history.call_count, 1)
        self.assertEqual(records, original)

    def test_missing_history_and_files_are_safe(self):
        payload = v2.calculate_current_streaks_v2([], [tracked()], reference_time=datetime.now(timezone.utc))
        self.assertEqual(payload["leagues"]["GT"], [])
        root = Path(__file__).parent / ".tmp"
        path = root / f"{uuid.uuid4().hex}.txt"
        try:
            path.write_text("GT|Lucas\n", encoding="utf-8")
            loaded = v2.load_current_streaks_v2(path, root / "missing-a", root / "missing-b", reference_time=datetime.now(timezone.utc))
            self.assertEqual(loaded["leagues"]["GT"], [])
        finally:
            if path.exists():
                path.unlink()

    def test_invalid_active_window_and_reference(self):
        for value in (0, -1, 1.5, True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                v2.calculate_current_streaks_v2([], [], reference_time=datetime.now(timezone.utc), active_window_minutes=value)
        with self.assertRaises(ValueError):
            v2.calculate_current_streaks_v2([], [], reference_time="now")


if __name__ == "__main__":
    unittest.main()
