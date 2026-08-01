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
        }],
    }


class CoincidentRenderingTests(unittest.TestCase):
    def test_section_pair_columns_madrid_time_results_and_gap(self):
        html = render_coincident_matches([pair()])
        self.assertIn("<h2>Coincident Matches</h2>", html)
        self.assertIn("GT · Lucas ↔ EADRIATIC · Dexter", html)
        for header in ("#", "Player A", "Time A", "Result A", "Opponent A", "Player B", "Time B", "Result B", "Opponent B", "Gap"):
            self.assertIn(f"<th>{header}</th>", html)
        self.assertIn("01/08/2026 10:15", html)
        self.assertIn(">V<", html)
        self.assertIn(">D<", html)
        self.assertIn("5 min", html)

    def test_same_league_empty_pair_and_no_selection(self):
        same = render_coincident_matches([pair([], "GT")])
        self.assertIn("GT · Lucas ↔ GT · Dexter", same)
        self.assertIn("No coincident matches within 30 minutes.", same)
        self.assertIn("No selected player combinations.", render_coincident_matches([]))

    def test_names_are_escaped_and_star_is_not_rendered(self):
        value = pair()
        value["player_a"] = "<Lucas>"
        html = render_coincident_matches([value])
        self.assertIn("&lt;Lucas&gt;", html)
        self.assertNotIn("<Lucas>", html)
        self.assertNotIn("*", html)

    def test_render_page_legacy_call_still_works(self):
        html = render_page({}, {})
        self.assertIn("Coincident Matches", html)
        self.assertIn("No selected player combinations.", html)

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
