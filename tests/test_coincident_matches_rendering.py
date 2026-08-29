import unittest

from web_tracker.generate_site import (
    load_current_streaks, render_coincident_matches, render_h2h_alerts, render_page,
)


def pair(matches=None, league_b="EADRIATIC"):
    return {
        "player_a_league": "GT", "player_a": "Lucas",
        "player_b_league": league_b, "player_b": "Dexter",
        "max_gap_minutes": 30,
        "matches": matches if matches is not None else [{
            "pair_order": 1, "player_a": "Lucas", "player_a_timestamp": "2026-08-01T08:15:00Z",
            "player_a_result": "V", "player_a_rival": "Fox",
            "player_b": "Dexter", "player_b_timestamp": "2026-08-01T08:20:00Z",
            "player_b_result": "D", "player_b_rival": "Eric", "gap_minutes": 5,
            "confirmation": "MIXED",
        }],
    }


def indicators(lucas_pct=80.0, dexter_pct=50.0):
    return {"leagues": {
        "GT": [{"player_key": "lucas", "indicator": "GREEN", "win_pct": lucas_pct}],
        "EADRIATIC": [{"player_key": "dexter", "indicator": "RED", "loss_pct": dexter_pct}],
    }}


class CoincidentRenderingTests(unittest.TestCase):
    def test_section_pair_columns_madrid_time_results_and_gap(self):
        html = render_coincident_matches([pair()], indicators())
        self.assertIn("<h2>Coincident Matches — Last 8 Hours</h2>", html)
        self.assertIn("GT · Lucas [NONE] ↔ EADRIATIC · Dexter [NONE]", html)
        for header in ("#", "Player A", "Time A", "Result A", "Opponent A", "Player B", "Time B", "Result B", "Opponent B", "Gap", "Confirmation"):
            self.assertIn(f"<th>{header}</th>", html)
        self.assertIn("01/08/2026 10:15", html)
        self.assertIn(">V<", html)
        self.assertIn(">D<", html)
        self.assertIn("5 min", html)

    def test_same_league_empty_pair_and_no_selection(self):
        same = render_coincident_matches([pair([], "GT")])
        self.assertIn("No pairs exceed the 35% combined threshold.", same)
        self.assertIn("No pairs exceed the 35% combined threshold.", render_coincident_matches([]))

    def test_names_are_escaped_and_star_is_not_rendered(self):
        value = pair()
        value["player_a"] = "<Lucas>"
        payload = indicators()
        payload["leagues"]["GT"][0]["player_key"] = "<lucas>"
        html = render_coincident_matches([value], payload)
        self.assertIn("&lt;Lucas&gt;", html)
        self.assertNotIn("<Lucas>", html)
        self.assertNotIn("*", html)

    def test_render_page_legacy_call_still_works(self):
        html = render_page({}, {})
        self.assertIn("Coincident Matches", html)
        self.assertIn("No pairs exceed the 35% combined threshold.", html)

    def test_combined_threshold_percentage_and_misses_since_hit(self):
        value = pair([
            {**pair()["matches"][0], "pair_order": 1, "confirmation": None},
            {**pair()["matches"][0], "pair_order": 2, "confirmation": None},
            {**pair()["matches"][0], "pair_order": 3, "confirmation": None},
            {**pair()["matches"][0], "pair_order": 4, "confirmation": "MIXED"},
            {**pair()["matches"][0], "pair_order": 5, "confirmation": None},
            {**pair()["matches"][0], "pair_order": 6, "confirmation": None},
        ])
        html = render_coincident_matches([value], indicators())
        self.assertIn("Combined: 40.00%", html)
        self.assertIn("Without a hit: 2", html)
        self.assertIn("Max without a hit: 3", html)

        self.assertNotIn("GT · Lucas", render_coincident_matches([value], indicators(50, 50)))

    def test_selected_player_remains_tracked_and_h2h_indicator_works(self):
        tracked = [{"league": "GT", "player": "Lucas", "player_key": "lucas", "tracked": True, "selected": True}]
        # No stats files are required to prove the canonical selected identity is accepted.
        streaks = load_current_streaks(tracked)
        self.assertIn("GT", streaks)
        html = render_h2h_alerts("GT", [{"player": "Lucas", "rival": "Fox", "signal": "WATCH"}], {("GT", "lucas"): "GREEN"})
        self.assertIn("GREEN Lucas", html)
        self.assertNotIn("Lucas*", html)


if __name__ == "__main__":
    unittest.main()
