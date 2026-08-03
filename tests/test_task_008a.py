from datetime import datetime, timezone
import unittest

import group_analysis
from coincident_matches import build_automatic_player_refs
from current_streaks_v2 import calculate_operational_snapshot
from match_history import name_key
from selected_players import parse_tracked_player_line


def record(player, rival="Fox"):
    return {
        "league": "GT", "player": player, "player_key": name_key(player),
        "rival": rival, "rival_key": name_key(rival), "result": "V",
        "timestamp_utc": "2026-08-03T10:00:00Z", "match_id": "gt:1",
        "perspective_id": f"gt:1:{name_key(player)}",
    }


class Task008AOperationalExclusionTests(unittest.TestCase):
    def test_star_is_real_tracked_player_but_not_bettable(self):
        row = parse_tracked_player_line("GT|Lucas*")
        self.assertEqual((row["player"], row["tracked"], row["bettable"], row["empty_slot"]),
                         ("Lucas", True, False, False))

    def test_unbettable_player_is_absent_from_snapshot_and_automatic_refs(self):
        player = parse_tracked_player_line("GT|Lucas*")
        snapshot = calculate_operational_snapshot(
            [record("Lucas")], [player],
            reference_time=datetime(2026, 8, 3, 11, tzinfo=timezone.utc),
        )
        self.assertEqual(snapshot, [])
        self.assertEqual(build_automatic_player_refs(snapshot), [])

    def test_h2h_excludes_principal_and_excluded_rival(self):
        result = {
            "league": "GT",
            "groups": [{"group_id": "g", "label": "Fox / Lucas", "h2h_matrix": [
                {"player": "Lucas", "rivals": [{"rival": "Fox", "W": 6, "D": 0, "L": 4, "matches": 10, "win_pct": 60.0, "draw_pct": 0.0, "loss_pct": 40.0}]},
                {"player": "Fox", "rivals": [{"rival": "Lucas", "W": 6, "D": 0, "L": 4, "matches": 10, "win_pct": 60.0, "draw_pct": 0.0, "loss_pct": 40.0}]},
            ]}],
        }
        alerts = group_analysis.calculate_h2h_alerts(
            result, operational_players={("GT", "fox")},
            excluded_keys={("GT", "lucas")},
        )
        self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
