import unittest

from web_tracker.generate_site import render_current_streaks_v2, render_page


def session(**overrides):
    row = {
        "player": "Lucas", "league": "GT", "wins": 3, "draws": 1,
        "losses": 2, "played": 6, "last_24": "VEDVVD", "win_pct": 50.0,
        "loss_pct": 33.33, "current_streak_result": "D", "current_streak": 1,
        "active": True, "balance": "🟢", "tracked": True, "group_index": 0,
    }
    row.update(overrides)
    return row


def payload(rows=None):
    return {
        "operational_window_hours": 8,
        "leagues": {"GT": rows if rows is not None else [session()], "EADRIATIC": []},
    }


class CurrentStreaksRenderingTests(unittest.TestCase):
    def test_v2_is_the_only_current_streaks_block_and_has_the_final_name(self):
        html = render_page({}, {}, [], payload())
        self.assertEqual(html.count("<h2>Current Streaks — Last 8 Hours</h2>"), 1)
        self.assertNotIn("Current Streaks V2", html)
        self.assertNotIn("Current Streaks — Legacy", html)
        for header in ("PLAYER", "W", "D", "L", "PLAYED", "LAST 24", "STREAK"):
            self.assertIn(f"<th>{header}</th>", html)

    def test_sequence_streak_balance_and_empty_payload(self):
        html = render_current_streaks_v2(payload())
        self.assertIn("VEDVVD", html)
        self.assertIn("D × 1", html)
        self.assertIn("🟢 Lucas", html)
        self.assertEqual(render_current_streaks_v2({}).count("Visible players: 0"), 2)

    def test_name_is_escaped(self):
        html = render_current_streaks_v2(payload([session(player="<Lucas>")]))
        self.assertIn("&lt;Lucas&gt;", html)
        self.assertNotIn("<Lucas>", html)


if __name__ == "__main__":
    unittest.main()
