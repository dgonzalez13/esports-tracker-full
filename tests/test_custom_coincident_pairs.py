from pathlib import Path
from datetime import datetime, timezone
import uuid
import unittest

import coincident_matches as cm
from selected_players import load_coincident_config, load_tracked_players
from tests.test_coincident_matches import event, ref
from web_tracker.generate_site import render_page


class DirectMatchesTests(unittest.TestCase):
    def direct(self):
        return [
            {**event("A", 10, rival="B"), "match_id": "direct"},
            {**event("B", 10, result="D", rival="A"), "match_id": "direct"},
        ]

    def match(self, records, indicators=("GREEN", "RED"), reverse=False):
        players = [{**ref(name), "indicator": indicator} for name, indicator in zip(("A", "B"), indicators)]
        if reverse:
            players.reverse()
        return cm.match_coincident_pair(players[0], records, players[1], records)["matches"]

    def test_equal_indicators_exclude_both_perspectives_even_with_nearby_matches(self):
        for indicator in ("GREEN", "RED"):
            rows = self.match(self.direct() + [event("A", 15, index=2), event("B", 20, index=2)], (indicator, indicator))
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["player_a_match_id"], rows[0]["player_b_match_id"]), ("A-2", "B-2"))

    def test_mixed_reserves_next_red_game_in_both_orientations_without_reuse(self):
        records = self.direct() + [event("B", 5, index=0), event("A", 15, index=2), event("B", 20, result="D", index=2)]
        for reverse in (False, True):
            rows = self.match(records, reverse=reverse)
            green, red = ("b", "a") if reverse else ("a", "b")
            special = next(r for r in rows if r[f"player_{green}_match_id"] == "direct")
            self.assertEqual(special[f"player_{red}_match_id"], "B-2")
            self.assertEqual(special["confirmation"], "MIXED")
            ids = [r[f"player_{side}_match_id"] for r in rows for side in ("a", "b")]
            self.assertEqual(len(ids), len(set(ids)))

    def test_next_result_is_not_cherry_picked(self):
        rows = self.match(self.direct() + [event("B", 15, result="V", index=2), event("B", 20, result="D", index=3)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_b_match_id"], "B-2")
        self.assertIsNone(rows[0]["confirmation"])

    def test_no_next_game_or_outside_gap_leaves_no_complete_pair(self):
        self.assertEqual(self.match(self.direct()), [])
        self.assertEqual(self.match(self.direct() + [event("B", 41, index=2)]), [])
        self.assertEqual(len(self.match(self.direct() + [event("B", 40, index=2)])), 1)

    def test_same_names_in_different_leagues_are_not_direct_opponents(self):
        a, b = {**ref("A"), "indicator": "GREEN"}, {**ref("B", "EADRIATIC"), "indicator": "GREEN"}
        rows = cm.match_coincident_pair(a, [event("A", 10, rival="B")], b, [event("B", 10, league="EADRIATIC", rival="A")])["matches"]
        self.assertEqual(len(rows), 1)


class CustomPairsTests(unittest.TestCase):
    def config(self, content):
        path = Path(__file__).parent / ".tmp" / f"{uuid.uuid4().hex}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(content, encoding="utf-8")
            config = load_coincident_config(path)
            self.assertEqual(load_tracked_players(path), [])
            return config
        finally:
            path.unlink(missing_ok=True)

    def test_parser_preserves_explicit_pairs_and_normalizes(self):
        config = self.config("@COINCIDENT_PAIR|| gt | A | green || eadriatic | B | red\n@COINCIDENT_PAIR||\n")
        a, b = config["custom_pairs"][0]
        self.assertEqual((a["league"], a["indicator"], b["player_key"]), ("GT", "GREEN", "b"))

    def test_invalid_and_duplicate_pairs_fail_with_line_number(self):
        for payload in ("GT|A|BLUE||GT|B|RED", "GT|A|GREEN", "GT|A|GREEN||GT|a|RED", "XXX|A|GREEN||GT|B|RED"):
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "line 1"):
                self.config("@COINCIDENT_PAIR||" + payload)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.config("@COINCIDENT_PAIR||GT|A|GREEN||GT|B|RED\n@COINCIDENT_PAIR||GT|B|RED||GT|A|GREEN")

    def test_three_pair_limit(self):
        lines = [f"@COINCIDENT_PAIR||GT|A{i}|GREEN||GT|B{i}|RED" for i in range(4)]
        self.assertEqual(len(self.config("\n".join(lines[:3]))["custom_pairs"]), 3)
        with self.assertRaisesRegex(ValueError, "at most 3"):
            self.config("\n".join(lines))

    def test_disabled_pairs_are_ignored_even_when_incomplete_and_can_be_reactivated(self):
        active = "@COINCIDENT_PAIR||GT|A|GREEN||EADRIATIC|B|RED"
        for prefix in ("*", "  * "):
            self.assertEqual(self.config(prefix + active)["custom_pairs"], [])
            self.assertEqual(self.config(prefix + "@COINCIDENT_PAIR||GT|Unfinished")["custom_pairs"], [])
        self.assertEqual(len(self.config(active)["custom_pairs"]), 1)
        lines = [f"@COINCIDENT_PAIR||GT|A{i}|GREEN||GT|B{i}|RED" for i in range(3)]
        self.assertEqual(len(self.config("\n".join(lines + ["*" + active, "*" + lines[0]]))["custom_pairs"]), 3)

    def test_custom_only_rendering_with_fixed_indicators_and_no_automatic_thresholds(self):
        config = self.config("@COINCIDENT_PAIR||GT|A|GREEN||GT|B|RED")
        result = cm.calculate_all_coincident_pairs(
            [event("A", 0), event("B", 5, result="D")], snapshot=[], custom_pairs=config["custom_pairs"],
        )
        self.assertEqual(len(result), 0)
        self.assertEqual(len(result.custom_pairs), 1)
        self.assertEqual(result.custom_pairs[0]["matches"][0]["confirmation"], "MIXED")
        html = render_page({}, {}, result)
        self.assertIn("Custom Pairs", html)
        self.assertIn("A [GREEN]", html)
        self.assertIn("B [RED]", html)
        self.assertIn("Combined: 100.00%", html)

    def test_empty_custom_pair_is_visible(self):
        config = self.config("@COINCIDENT_PAIR||GT|A|GREEN||GT|B|RED")
        result = cm.calculate_all_coincident_pairs([], custom_pairs=config["custom_pairs"])
        self.assertIn("A [GREEN]", render_page({}, {}, result))

    def test_custom_pairs_keep_window_exclusions_and_do_not_create_other_combinations(self):
        config = self.config("@COINCIDENT_PAIR||GT|A|GREEN||GT|B|RED\n@COINCIDENT_PAIR||GT|C|RED||GT|D|RED")
        records = [event("A", 0), event("B", 5, result="D"),
                   event("A", 20, index=2), event("B", 25, index=2),
                   event("C", 1, rival="Excluded"), event("D", 2)]
        result = cm.calculate_all_coincident_pairs(
            records, custom_pairs=config["custom_pairs"],
            reference_time=datetime(2026, 8, 1, 10, 10, tzinfo=timezone.utc),
            excluded_keys={("GT", "excluded")},
        )
        self.assertEqual(len(result), 0)
        self.assertEqual(result.groups, [])
        self.assertEqual(len(result.custom_pairs), 2)
        self.assertEqual(len(result.custom_pairs[0]["matches"]), 1)
        self.assertEqual(result.custom_pairs[1]["matches"], [])


if __name__ == "__main__":
    unittest.main()
