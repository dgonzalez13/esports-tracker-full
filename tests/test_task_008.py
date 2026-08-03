from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import group_analysis
from coincident_matches import build_automatic_player_refs, calculate_all_coincident_pairs
from current_streaks_v2 import calculate_operational_snapshot
from match_history import name_key
from selected_players import parse_tracked_player_line


def tracked(name, league="GT"):
    return {"league": league, "player": name, "player_key": name_key(name), "tracked": True, "selected": False}


def event(name, result, when, index, league="GT"):
    return {"league": league, "player": name, "player_key": name_key(name),
            "rival": "Opponent", "rival_key": name_key("Opponent"), "result": result,
            "timestamp_utc": when.isoformat().replace("+00:00", "Z"), "match_id": str(index), "perspective_id": str(index)}


class OperationalSnapshotTests(unittest.TestCase):
    def test_window_boundaries_future_selection_and_confirmation(self):
        now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
        rows = []
        for index, result in enumerate("VVVDD"):
            rows.append(event("Green", result, now - timedelta(minutes=index * 5), index))
        for index, result in enumerate("DDDVV", 10):
            rows.append(event("Red", result, now - timedelta(minutes=(index - 10) * 5 + 2), index))
        rows += [event("Green", "D", now - timedelta(hours=8), 30),
                 event("Green", "V", now - timedelta(hours=8, seconds=1), 31),
                 event("Green", "V", now + timedelta(seconds=1), 32)]
        snapshot = calculate_operational_snapshot(rows, [tracked("Green"), tracked("Red")], reference_time=now)
        green = next(row for row in snapshot if row["player"] == "Green")
        self.assertEqual((green["played"], green["indicator"]), (6, "GREEN"))
        refs = build_automatic_player_refs(snapshot)
        self.assertEqual([row["indicator"] for row in refs], ["RED", "GREEN"])
        pairs = calculate_all_coincident_pairs(rows, snapshot=snapshot, reference_time=now)
        self.assertTrue(all(row["confirmation"] in {"MIXED", None} for row in pairs[0]["matches"]))

    def test_empty_slot(self):
        empty = parse_tracked_player_line("GT|*")
        self.assertTrue(empty["empty_slot"])
        self.assertFalse(empty["tracked"])
        self.assertEqual(empty["player"], "")

    def test_empty_slot_preserves_five_position_group(self):
        entries = [parse_tracked_player_line(value) for value in (
            "GT|A", "GT|B", "GT|", "GT|C", "GT|D", "GT|Next",
        )]
        with patch.object(group_analysis, "load_tracked_players", return_value=entries):
            groups = group_analysis.load_groups()
        self.assertEqual(groups["GT"], [["A", "B", "C", "D"], ["Next"]])

    def test_five_empty_slots_do_not_create_a_group(self):
        entries = [parse_tracked_player_line("GT|") for _ in range(5)]
        with patch.object(group_analysis, "load_tracked_players", return_value=entries):
            groups = group_analysis.load_groups()
        self.assertEqual(groups["GT"], [])


if __name__ == "__main__":
    unittest.main()
