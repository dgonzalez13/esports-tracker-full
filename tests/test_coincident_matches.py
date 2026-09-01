import copy
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import coincident_matches as cm
from match_history import name_key


def ref(player="Alice", league="GT"):
    return {"league": league, "player": player, "player_key": name_key(player)}


def event(player, minute, result="V", league="GT", rival="Rival", index=1, timestamp=None):
    stamp = timestamp or f"2026-08-01T10:{minute:02d}:00Z"
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "rival": rival, "rival_key": name_key(rival), "result": result,
        "timestamp_utc": stamp, "match_id": f"{player}-{index}",
        "perspective_id": f"{player}-{index}:{name_key(player)}",
    }


class ModelsSelectionAndHistoryTests(unittest.TestCase):
    def test_models_have_exact_shapes(self):
        self.assertEqual(cm.SelectedPlayerRef.__required_keys__, frozenset({"league", "player", "player_key"}))
        self.assertEqual(cm.CoincidentPairAnalysis.__required_keys__, frozenset({
            "player_a_league", "player_a", "player_b_league", "player_b",
            "player_a_indicator", "player_b_indicator", "max_gap_minutes",
            "operational_window_hours", "matches",
        }))
        self.assertEqual(cm.CoincidentMatch.__required_keys__, frozenset({
            "player_a_league", "player_a", "player_a_match_id", "player_a_timestamp",
            "player_a_result", "player_a_rival", "player_b_league", "player_b",
            "player_b_match_id", "player_b_timestamp", "player_b_result",
            "player_b_rival", "gap_minutes", "pair_order", "confirmation",
        }))

    def test_build_refs_and_all_three_combinations(self):
        tracked = [
            {**ref("B", "GT"), "tracked": True, "selected": True},
            {**ref("A", "GT"), "tracked": True, "selected": True},
            {**ref("A", "EADRIATIC"), "tracked": True, "selected": True},
            {**ref("X", "GT"), "tracked": True, "selected": False},
        ]
        refs = cm.build_selected_player_refs(tracked)
        self.assertEqual([(r["league"], r["player"]) for r in refs], [("EADRIATIC", "A"), ("GT", "A"), ("GT", "B")])
        self.assertEqual(len(cm.generate_selected_pairs(refs)), 3)
        self.assertEqual(cm.generate_selected_pairs(refs[:1]), [])

    def test_history_filters_identity_result_and_timestamp_and_sorts(self):
        player = ref()
        records = [
            event("Alice", 5, index=2), event("Alice", 0, index=1),
            event("Bob", 1, rival="Alice"), event("Alice", 2, result="X"),
            event("Alice", 3, timestamp="broken"), event("Alice", 4, league="EADRIATIC"),
        ]
        original = copy.deepcopy(records)
        rows = cm.player_match_history(records, player)
        self.assertEqual([row["match_id"] for row in rows], ["Alice-1", "Alice-2"])
        rows[0]["result"] = "D"
        self.assertEqual(records, original)

    def test_timestamp_z_offset_naive_are_normalized(self):
        player = ref()
        records = [
            event("Alice", 0, index=1, timestamp="2026-08-01T12:00:00+02:00"),
            event("Alice", 0, index=2, timestamp="2026-08-01T10:01:00"),
            event("Alice", 0, index=3, timestamp="2026-08-01T10:02:00Z"),
        ]
        self.assertEqual([r["match_id"] for r in cm.player_match_history(records, player)], ["Alice-1", "Alice-2", "Alice-3"])


class MatchingTests(unittest.TestCase):
    def pair(self, a_events, b_events, gap=30):
        return cm.match_coincident_pair(ref("A"), a_events, ref("B"), b_events, max_gap_minutes=gap)

    def test_exact_five_thirty_and_thirty_one_minutes(self):
        for minute, expected in ((0, 0), (5, 5), (30, 30)):
            row = self.pair([event("A", 0)], [event("B", minute)])["matches"][0]
            self.assertEqual(row["gap_minutes"], expected)
        self.assertEqual(self.pair([event("A", 0)], [event("B", 31)])["matches"], [])

    def test_immediately_previous_is_chosen(self):
        a = [event("A", 0, index=1), event("A", 20, index=2), event("A", 55, index=3, timestamp="2026-08-01T10:55:00Z")]
        b = [event("B", 0, timestamp="2026-08-01T11:00:00Z")]
        row = self.pair(a, b)["matches"][0]
        self.assertEqual(row["player_a_match_id"], "A-3")

    def test_never_future_no_reuse_and_alternation(self):
        a = [event("A", 0, index=1), event("A", 15, index=2), event("A", 40, index=3)]
        b = [event("B", 5, index=1), event("B", 10, index=2), event("B", 25, index=3), event("B", 50, index=4)]
        rows = self.pair(a, b)["matches"]
        self.assertEqual([(r["player_a_match_id"], r["player_b_match_id"]) for r in rows], [("A-1", "B-1"), ("A-2", "B-2"), ("A-3", "B-3")])
        self.assertEqual([r["pair_order"] for r in rows], [1, 2, 3])

    def test_equal_timestamp_input_order_and_orientation_are_stable(self):
        a, b = event("A", 0, result="V"), event("B", 0, result="D")
        first = self.pair([a], [b])
        second = self.pair(reversed([a]), reversed([b]))
        self.assertEqual(first, second)
        row = first["matches"][0]
        self.assertEqual((row["player_a"], row["player_a_result"], row["player_b"], row["player_b_result"]), ("A", "V", "B", "D"))

    def test_seconds_are_truncated_for_public_gap(self):
        a = event("A", 0, timestamp="2026-08-01T10:00:30Z")
        b = event("B", 0, timestamp="2026-08-01T10:05:29Z")
        self.assertEqual(self.pair([a], [b])["matches"][0]["gap_minutes"], 4)

    def test_invalid_gap(self):
        for value in (-1, 1.5, "30", None, True, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.pair([], [], value)

    def test_all_pairs_include_empty_and_build_each_history_once(self):
        players = [ref("A"), ref("B"), ref("C", "EADRIATIC")]
        records = [event("A", 0), event("B", 5)]
        with patch.object(cm, "player_match_history", wraps=cm.player_match_history) as history:
            rows = cm.calculate_all_coincident_pairs(records, players)
        self.assertEqual(len(rows), 3)
        self.assertEqual(history.call_count, 3)
        self.assertTrue(any(not row["matches"] for row in rows))

    def test_triples_and_quartets_are_generated_without_changing_pair_list(self):
        players = [
            {**ref(name), "indicator": "GREEN", "group_index": index // 2}
            for index, name in enumerate(("A", "B", "C", "D"))
        ]
        records = [event(name, minute, index=minute + 1) for minute, name in enumerate(("A", "B", "C", "D"))]
        result = cm.calculate_all_coincident_pairs(records, players)
        self.assertEqual(len(result), 6)
        self.assertEqual([group["size"] for group in result.groups].count(3), 4)
        self.assertEqual([group["size"] for group in result.groups].count(4), 1)
        quartet = next(group for group in result.groups if group["size"] == 4)
        self.assertEqual(len(quartet["matches"]), 1)
        self.assertEqual(quartet["matches"][0]["confirmation"], "ALL_GREEN")
        self.assertEqual(quartet["matches"][0]["gap_minutes"], 3)
        self.assertFalse(quartet["different_groups"])
        self.assertTrue(any(pair["different_groups"] for pair in result))

    def test_group_highlight_requires_every_player_to_have_a_distinct_group(self):
        players = [
            {**ref(name), "indicator": "GREEN", "group_index": index}
            for index, name in enumerate(("A", "B", "C", "D"))
        ]
        result = cm.calculate_all_coincident_pairs([], players)
        self.assertTrue(all(group["different_groups"] for group in result.groups))

        players[3]["group_index"] = 2
        result = cm.calculate_all_coincident_pairs([], players)
        quartet = next(group for group in result.groups if group["size"] == 4)
        self.assertFalse(quartet["different_groups"])

    def test_groups_never_contain_more_than_two_players_from_one_tracked_group(self):
        players = [
            {**ref(name), "indicator": "GREEN", "group_index": 0 if name != "D" else 1}
            for name in ("A", "B", "C", "D")
        ]
        result = cm.calculate_all_coincident_pairs([], players)
        identities = [
            [(player["league"], player["group_index"]) for player in group["players"]]
            for group in result.groups
        ]
        self.assertEqual(len(result.groups), 3)
        self.assertTrue(all(max(keys.count(key) for key in set(keys)) <= 2 for keys in identities))

    def test_loader_tolerates_one_or_both_missing_jsonl(self):
        root = Path(__file__).parent / ".tmp"
        tracked = root / f"{uuid.uuid4().hex}.txt"
        try:
            tracked.write_text("GT|A*\nGT|B*\n", encoding="utf-8")
            self.assertEqual(len(cm.load_all_coincident_pairs(tracked, root / "a", root / "b")), 0)
        finally:
            if tracked.exists():
                tracked.unlink()


if __name__ == "__main__":
    unittest.main()
