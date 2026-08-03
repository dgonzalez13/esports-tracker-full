from pathlib import Path
import unittest
import uuid

from selected_players import (
    TrackedPlayer, load_tracked_players, parse_tracked_player_line,
    selected_player_keys, tracked_player_keys,
)


class SelectedPlayersTests(unittest.TestCase):
    def test_model_has_exact_keys(self):
        self.assertEqual(TrackedPlayer.__required_keys__, frozenset({
            "league", "player", "player_key", "tracked", "selected",
        }))

    def test_normal_selected_spaces_unicode_and_league(self):
        normal = parse_tracked_player_line(" gt | Lucas ")
        selected = parse_tracked_player_line(" eadriatic |  João Silva  * ")
        self.assertEqual((normal["league"], normal["player"], normal["selected"]), ("GT", "Lucas", False))
        self.assertEqual((selected["league"], selected["player"], selected["selected"]), ("EADRIATIC", "João Silva", True))
        self.assertNotIn("*", selected["player"])
        self.assertTrue(normal["tracked"] and selected["tracked"])

    def test_empty_line(self):
        self.assertIsNone(parse_tracked_player_line("  \n"))

    def test_invalid_lines_raise_clear_errors(self):
        for value in ("Lucas", "|Lucas"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_tracked_player_line(value)
        for value in ("GT|", "GT| *"):
            with self.subTest(value=value):
                self.assertTrue(parse_tracked_player_line(value)["empty_slot"])

    def test_load_deduplicates_promotes_selection_and_preserves_order(self):
        path = Path(__file__).parent / ".tmp" / f"{uuid.uuid4().hex}.txt"
        content = "GT|Lucas\nEADRIATIC|Dexter\nGT|Lucas*\n\n"
        try:
            path.write_text(content, encoding="utf-8")
            rows = load_tracked_players(path)
            self.assertEqual([row["player"] for row in rows], ["Lucas", "Dexter"])
            self.assertTrue(rows[0]["selected"])
            self.assertFalse(rows[1]["selected"])
            self.assertEqual(path.read_text(encoding="utf-8"), content)
        finally:
            if path.exists():
                path.unlink()

    def test_missing_file_and_key_helpers(self):
        self.assertEqual(load_tracked_players("definitely-missing-tracked.txt"), [])
        rows = [parse_tracked_player_line("GT|Lucas*"), parse_tracked_player_line("GT|Fox")]
        self.assertEqual(tracked_player_keys(rows), {("GT", "lucas"), ("GT", "fox")})
        self.assertEqual(selected_player_keys(rows), {("GT", "lucas")})


if __name__ == "__main__":
    unittest.main()
