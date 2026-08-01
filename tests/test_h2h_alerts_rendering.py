import unittest

from web_tracker.generate_site import render_h2h_alerts


def alert(**overrides):
    row = {
        "player": "David", "rival": "Fox", "W": 30, "D": 5, "L": 15,
        "matches": 50, "win_pct": 60.0, "signal": "STRONG",
        "recent_window": 20, "recent_available": 8,
        "recent_sequence": "VEDDVVVV", "recent_win_pct": 62.5,
        "recent_win_pct_delta": 2.5, "recent_trend": "STABLE",
        "recent_sample_status": "LOW_SAMPLE", "recent_window_complete": False,
        "last10": "SHOULD_NOT_RENDER", "stk_win": 9, "stk_lose": 8,
    }
    row.update(overrides)
    return row


class H2HAlertRenderingTests(unittest.TestCase):
    def test_new_columns_and_order_replace_legacy_streak_columns(self):
        html = render_h2h_alerts("GT", [alert()], {})
        headers = ["Player", "Rival", "W", "D", "L", "Matches", "Win %", "Last 20", "Win % L20", "Trend", "Signal", "Sample"]
        positions = [html.index(f"<th>{header}</th>") for header in headers]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("STK WIN", html)
        self.assertNotIn("STK LOSE", html)
        self.assertNotIn("SHOULD_NOT_RENDER", html)

    def test_partial_sequence_percentage_trend_and_sample(self):
        html = render_h2h_alerts("GT", [alert()], {})
        self.assertIn("VEDDVVVV", html)
        self.assertNotIn("VVVVDDEV", html)
        self.assertIn("62.50%", html)
        self.assertIn("→ +2.50", html)
        self.assertIn("8/20 · LOW", html)
        self.assertNotIn("<span class=\"result", html)

    def test_complete_up_down_and_empty_format(self):
        complete = alert(recent_available=20, recent_window_complete=True, recent_sample_status="COMPLETE", recent_trend="UP", recent_win_pct_delta=12.5)
        down = alert(recent_trend="DOWN", recent_win_pct_delta=-18.25)
        empty = alert(recent_available=0, recent_sequence="", recent_sample_status="EMPTY", recent_trend=None)
        html = render_h2h_alerts("GT", [complete, down, empty], {})
        self.assertIn("20/20", html)
        self.assertIn("↑ +12.50", html)
        self.assertIn("↓ -18.25", html)
        self.assertGreaterEqual(html.count("—"), 4)

    def test_player_rival_indicators_and_escaping_are_preserved(self):
        row = alert(player="<David>", rival="Fox & Co")
        lookup = {("GT", "<david>"): "GREEN", ("GT", "fox & co"): "RED"}
        html = render_h2h_alerts("GT", [row], lookup)
        self.assertIn("GREEN &lt;David&gt;", html)
        self.assertIn("RED Fox &amp; Co", html)
        self.assertNotIn("<David>", html)

    def test_legacy_json_uses_dashes_and_empty_table_stays_hidden(self):
        legacy = {"player": "David", "rival": "Fox", "signal": "WATCH", "last10": "VVVV"}
        html = render_h2h_alerts("GT", [legacy], {})
        self.assertGreaterEqual(html.count("—"), 4)
        self.assertNotIn("VVVV", html)
        self.assertEqual(render_h2h_alerts("GT", [], {}), "")


if __name__ == "__main__":
    unittest.main()
