import unittest

from web_tracker.generate_site import (
    render_current_streaks, render_current_streaks_v2, render_page,
)


def session(**overrides):
    row = {
        "player": "Lucas", "league": "GT", "start_local": "2026-08-01T22:00:00+02:00",
        "end_local": "2026-08-02T01:55:00+02:00", "duration_minutes": 235,
        "wins": 3, "draws": 1, "losses": 2, "played": 6, "last_10": "VEDVVD",
        "win_pct": 50.0, "loss_pct": 33.33,
        "current_streak_result": "D", "current_streak": 1, "active": True,
        "balance": "🟢", "tracked": True,
    }
    row.update(overrides)
    return row


def payload(rows=None):
    return {
        "operational_window_hours": 8,
        "leagues": {"GT": rows if rows is not None else [session()], "EADRIATIC": []},
    }


class CurrentStreaksV2RenderingTests(unittest.TestCase):
    def test_legacy_title_and_columns_are_preserved(self):
        legacy = {"GT": {"title": "GT League", "source": "daily.txt", "rows": []}}
        html = render_current_streaks(legacy)
        self.assertIn("Current Streaks — Legacy", html)
        for header in ("STK WIN", "STK LOSE", "SEQ"):
            self.assertIn(f"<th>{header}</th>", html)

    def test_v2_title_audit_badges_columns_and_no_legacy_streaks(self):
        html = render_current_streaks_v2(payload())
        self.assertIn("Current Streaks V2 — Last 8 Hours", html)
        self.assertIn("Window: 8 hours", html)
        self.assertIn("Source: match_history.jsonl", html)
        for header in ("PLAYER", "W", "D", "L", "PLAYED", "LAST 10", "STREAK"):
            self.assertIn(f"<th>{header}</th>", html)
        self.assertNotIn("STK WIN", html)
        self.assertNotIn("STK LOSE", html)

    def test_midnight_duration_last10_streak_active_and_balance(self):
        html = render_current_streaks_v2(payload())
        self.assertIn("VEDVVD", html)
        self.assertIn("D × 1", html)
        self.assertIn("🟢 Lucas", html)

    def test_inactive_red_escaped_name_and_no_star(self):
        html = render_current_streaks_v2(payload([session(player="<Lucas>", active=False, balance="🔴")]))
        self.assertIn("🔴 &lt;Lucas&gt;", html)
        self.assertIn("&lt;Lucas&gt;", html)
        self.assertNotIn("<Lucas>", html)
        self.assertNotIn("*", html)

    def test_empty_payload_is_safe(self):
        html = render_current_streaks_v2({})
        self.assertIn("Current Streaks V2 — Last 8 Hours", html)
        self.assertEqual(html.count("Visible players: 0"), 2)

    def test_page_order_and_legacy_signature_compatibility(self):
        html = render_page({}, {}, [], payload())
        positions = [
            html.index("Current Streaks — Legacy"),
            html.index("Current Streaks V2 — Last 8 Hours"),
            html.index("Coincident Matches"),
            html.index("<h2>Group Analysis</h2>"),
        ]
        self.assertEqual(positions, sorted(positions))
        legacy_call = render_page({}, {})
        self.assertIn("Current Streaks V2 — Last 8 Hours", legacy_call)
        self.assertIn("Coincident Matches", legacy_call)


if __name__ == "__main__":
    unittest.main()
