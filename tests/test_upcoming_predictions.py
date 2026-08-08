import unittest

from upcoming_predictions import calculate_upcoming_predictions
from web_tracker.generate_site import render_coincident_matches, render_upcoming_predictions


def tracked(name, group=0, league="GT", bettable=True):
    return {
        "league": league,
        "player": name,
        "player_key": name.casefold(),
        "tracked": True,
        "selected": False,
        "bettable": bettable,
        "group_index": group,
    }


def perspective(player, rival, result, index, league="GT"):
    return {
        "league": league,
        "player": player,
        "player_key": player.casefold(),
        "rival": rival,
        "rival_key": rival.casefold(),
        "result": result,
        "timestamp_utc": f"2026-07-{(index % 28) + 1:02d}T08:{index % 60:02d}:00Z",
        "match_id": f"{league}:{index}:{player}:{rival}",
        "perspective_id": f"{league}:{index}:{player.casefold()}",
    }


class UpcomingPredictionsTests(unittest.TestCase):
    def test_high_estimate_is_generated_only_inside_same_group(self):
        players = [tracked("Alpha"), tracked("Beta"), tracked("Gamma", group=1)]
        records = []
        for i in range(30):
            records.append(perspective("Alpha", "Beta", "V", i))
            records.append(perspective("Beta", "Alpha", "D", i + 100))
        predictions = calculate_upcoming_predictions(records, players)
        self.assertEqual(len(predictions), 1)
        row = predictions[0]
        self.assertEqual((row["predicted_player"], row["opponent"]), ("Alpha", "Beta"))
        self.assertGreaterEqual(row["estimated_win_pct"], 65.0)
        self.assertEqual(row["confidence"], "HIGH")

    def test_unbettable_player_is_not_a_candidate_and_its_records_are_excluded(self):
        players = [tracked("Alpha"), tracked("Beta", bettable=False), tracked("Gamma")]
        records = []
        for i in range(30):
            records.append(perspective("Alpha", "Beta", "V", i))
            records.append(perspective("Beta", "Alpha", "D", i + 100))
        predictions = calculate_upcoming_predictions(records, players)
        self.assertEqual(predictions, [])

    def test_low_confidence_is_not_rendered_even_above_threshold(self):
        players = [tracked("Alpha"), tracked("Beta")]
        records = []
        for i in range(6):
            records.append(perspective("Alpha", "Beta", "V", i))
            records.append(perspective("Beta", "Alpha", "D", i + 100))
        predictions = calculate_upcoming_predictions(records, players)
        self.assertEqual(predictions, [])

    def test_threshold_is_configurable_and_validation_is_clear(self):
        self.assertEqual(calculate_upcoming_predictions([], [tracked("A"), tracked("B")], min_estimated_win_pct=90), [])
        with self.assertRaises(ValueError):
            calculate_upcoming_predictions([], [], min_estimated_win_pct=49)

    def test_rendering_labels_estimate_as_heuristic_not_probability(self):
        html = render_upcoming_predictions([{
            "league": "GT", "group_index": 0, "player_a": "Alpha", "player_b": "Beta",
            "predicted_player": "Alpha", "opponent": "Beta", "estimated_win_pct": 72.5,
            "confidence": "HIGH", "h2h_matches": 30, "h2h_win_pct": 70.0,
            "recent_h2h_matches": 20, "recent_h2h_win_pct": 75.0,
            "recent_player_matches": 24, "recent_player_win_pct": 66.67,
            "recent_opponent_matches": 24, "recent_opponent_loss_pct": 70.83,
            "overall_player_matches": 100, "overall_player_win_pct": 60.0,
            "overall_opponent_matches": 100, "overall_opponent_loss_pct": 62.0,
        }])
        self.assertIn("Upcoming Match Predictions", html)
        self.assertIn("Alpha WIN", html)
        self.assertIn("72.50%", html)
        self.assertIn("heuristic scores, not calibrated probabilities", html)


    def test_coincident_pairs_are_collapsed_and_reliable_block_is_rendered(self):
        class PairList(list):
            eligible_players = 2
            selected_candidates = 2
            candidate_limit = 8
            selection_mode = "automatic"
            excluded_candidates = 0

        pair = {
            "player_a_league": "GT",
            "player_a": "Alpha",
            "player_a_indicator": "GREEN",
            "player_b_league": "GT",
            "player_b": "Beta",
            "player_b_indicator": "RED",
            "max_gap_minutes": 30,
            "operational_window_hours": 8,
            "matches": [
                {
                    "pair_order": i + 1,
                    "player_a": "Alpha",
                    "player_a_timestamp": f"2026-08-08T10:{i:02d}:00Z",
                    "player_a_result": "V",
                    "player_a_rival": "X",
                    "player_b": "Beta",
                    "player_b_timestamp": f"2026-08-08T10:{i:02d}:00Z",
                    "player_b_result": "D",
                    "player_b_rival": "Y",
                    "gap_minutes": 0,
                    "confirmation": "MIXED",
                }
                for i in range(8)
            ],
        }
        v2 = {
            "leagues": {
                "GT": [
                    {
                        "player_key": "alpha",
                        "indicator": "GREEN",
                        "win_pct": 75.0,
                        "loss_pct": 10.0,
                    },
                    {
                        "player_key": "beta",
                        "indicator": "RED",
                        "win_pct": 10.0,
                        "loss_pct": 75.0,
                    },
                ]
            }
        }
        html = render_coincident_matches(PairList([pair]), v2)
        self.assertIn('<details class="coincident-pair">', html)
        self.assertNotIn('<details class="coincident-pair" open', html)
        self.assertIn("Most Reliable Coincident Pairs", html)
        self.assertIn("Reliability", html)
        self.assertIn("HIGH", html)


if __name__ == "__main__":
    unittest.main()
