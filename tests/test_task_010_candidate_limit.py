import unittest

from coincident_matches import (
    MAX_AUTOMATIC_CANDIDATES, build_automatic_player_refs,
    calculate_all_coincident_pairs,
)
from web_tracker.generate_site import render_coincident_matches


def candidate(name, *, league="GT", indicator="GREEN", played=5, pct=60.0):
    wins = round(played * pct / 100) if indicator == "GREEN" else 0
    losses = round(played * pct / 100) if indicator == "RED" else played - wins
    return {
        "league": league, "player": name, "player_key": name.casefold(),
        "indicator": indicator, "played": played, "wins": wins,
        "draws": played - wins - losses, "losses": losses,
        "win_pct": pct if indicator == "GREEN" else 0.0,
        "loss_pct": pct if indicator == "RED" else round(losses / played * 100, 2),
    }


class AutomaticCandidateLimitTests(unittest.TestCase):
    def test_public_limit(self):
        self.assertEqual(MAX_AUTOMATIC_CANDIDATES, 8)

    def test_fewer_than_and_exactly_eight_are_preserved(self):
        fewer = [candidate(f"P{i}", pct=50 + i) for i in range(1, 6)]
        exact = [candidate(f"P{i}", pct=50 + i) for i in range(1, 9)]
        self.assertEqual(len(build_automatic_player_refs(fewer)), 5)
        self.assertEqual(len(build_automatic_player_refs(exact)), 8)

    def test_more_than_eight_keeps_strongest_and_caps_pairs_at_28(self):
        snapshot = [candidate(f"P{i:02d}", pct=50 + i) for i in range(1, 11)]
        selected = build_automatic_player_refs(snapshot)
        self.assertEqual([row["player"] for row in selected], [
            "P10", "P09", "P08", "P07", "P06", "P05", "P04", "P03",
        ])
        pairs = calculate_all_coincident_pairs([], snapshot=snapshot)
        self.assertEqual(len(pairs), 28)
        self.assertEqual((pairs.eligible_players, pairs.selected_candidates, pairs.candidate_limit), (10, 8, 8))

    def test_ties_use_played_then_league_and_name_deterministically(self):
        snapshot = [
            candidate("Zulu", indicator="RED", played=5, pct=60),
            candidate("Alpha", league="GT", played=10, pct=60),
            candidate("Beta", league="EADRIATIC", played=10, pct=60),
            candidate("Able", league="GT", played=10, pct=60),
        ]
        expected = [("EADRIATIC", "Beta"), ("GT", "Able"), ("GT", "Alpha"), ("GT", "Zulu")]
        for rows in (snapshot, list(reversed(snapshot))):
            self.assertEqual(
                [(row["league"], row["player"]) for row in build_automatic_player_refs(rows)],
                expected,
            )

    def test_green_red_and_existing_green_priority_at_fifty_fifty(self):
        rows = [
            candidate("Green", indicator="GREEN", pct=70),
            candidate("Red", indicator="RED", pct=65),
            {**candidate("Tie", indicator="GREEN", played=6, pct=50),
             "wins": 3, "draws": 0, "losses": 3, "loss_pct": 50.0},
        ]
        selected = build_automatic_player_refs(rows)
        self.assertEqual([row["indicator"] for row in selected], ["GREEN", "RED", "GREEN"])

    def test_visible_selection_summary_with_and_without_pairs(self):
        pairs = calculate_all_coincident_pairs([], snapshot=[candidate(f"P{i}") for i in range(10)])
        html = render_coincident_matches(pairs)
        self.assertIn("Eligible players: 10", html)
        self.assertIn("Selected candidates: 8", html)
        self.assertIn("Candidate limit: 8", html)


if __name__ == "__main__":
    unittest.main()
