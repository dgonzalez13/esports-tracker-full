from datetime import datetime, timezone
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import group_analysis
from coincident_matches import build_selected_player_refs, calculate_all_coincident_pairs
from current_streaks_v2 import calculate_current_streaks_v2
from match_history import name_key
from selected_players import load_tracked_players, tracked_player_keys
from web_tracker.generate_site import load_current_streaks, render_h2h_alerts


def perspective(player="Lucas", league="GT"):
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "rival": "Fox", "rival_key": "fox", "result": "V",
        "timestamp_utc": "2026-08-01T08:00:00Z", "match_id": f"{league}:{player}",
        "perspective_id": f"{league}:{name_key(player)}",
    }


class TrackedMarkerConsumerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).parent / ".tmp" / f"{uuid.uuid4().hex}.txt"
        self.path.write_text(
            "GT|Lucas*\nGT|Fox\nGT|Kratos\nGT|Furious\nGT|Vendetta\n"
            "EADRIATIC|Eric*\n",
            encoding="utf-8",
        )
        self.players = load_tracked_players(self.path)

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_canonical_names_and_selection_are_preserved(self):
        lucas, eric = self.players[0], self.players[-1]
        self.assertEqual((lucas["league"], lucas["player"], lucas["tracked"], lucas["selected"]), ("GT", "Lucas", True, True))
        self.assertEqual((eric["league"], eric["player"], eric["selected"]), ("EADRIATIC", "Eric", True))
        self.assertFalse(self.players[1]["selected"])
        self.assertTrue(all(not row["player"].endswith("*") for row in self.players))

    def test_group_analysis_uses_clean_names(self):
        with patch.object(group_analysis, "BASE", self.path.parent), patch.object(
            group_analysis, "load_tracked_players", return_value=self.players[:5]
        ):
            groups = group_analysis.load_groups()
        self.assertEqual(groups["GT"][0][0], "Lucas")
        self.assertTrue(all(not player.endswith("*") for rows in groups.values() for group in rows for player in group))

    def test_v2_and_coincident_matches_use_clean_selected_identity(self):
        records = [perspective(), perspective("Eric", "EADRIATIC")]
        payload = calculate_current_streaks_v2(
            records, self.players,
            reference_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(payload["leagues"]["GT"][0]["player"], "Lucas")
        refs = build_selected_player_refs(self.players)
        self.assertEqual([row["player"] for row in refs], ["Eric", "Lucas"])
        pairs = calculate_all_coincident_pairs(records, refs)
        self.assertEqual((pairs[0]["player_a"], pairs[0]["player_b"]), ("Eric", "Lucas"))

    def test_legacy_tracking_and_h2h_indicator_use_clean_key(self):
        keys = tracked_player_keys(self.players)
        self.assertIn(("GT", "lucas"), keys)
        streaks = load_current_streaks(self.players)
        lucas_rows = [row for row in streaks["GT"]["rows"] if row["player"] == "Lucas"]
        self.assertTrue(lucas_rows and lucas_rows[0]["tracked"])
        html = render_h2h_alerts(
            "GT", [{"player": "Lucas", "rival": "Fox", "signal": "WATCH"}],
            {("GT", "lucas"): "GREEN"},
        )
        self.assertIn("GREEN Lucas", html)
        self.assertNotIn("Lucas*", html)

    def test_no_manual_tracked_file_parser_remains(self):
        root = Path(__file__).resolve().parent.parent
        consumers = [root / "group_analysis.py", root / "build_opportunity_input.py"]
        for source in consumers:
            text = source.read_text(encoding="utf-8")
            self.assertIn("load_tracked_players", text)
            self.assertNotIn('split("|"', text)


if __name__ == "__main__":
    unittest.main()
