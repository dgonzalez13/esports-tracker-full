import unittest

from web_tracker.generate_site import render_current_streaks_v2, render_long_current_runs, render_page


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
    def test_long_runs_filter_sort_and_combine_leagues(self):
        data = payload([
            session(player="Five", sequence="VDDDDD"),
            session(player="Below", sequence="VDDDD"),
            session(player="Both", sequence="EEEEEE"),
        ])
        data["leagues"]["EADRIATIC"] = [session(player="<Seven>", sequence="DVVVVVVV")]
        html = render_long_current_runs(data)
        self.assertNotIn("Below", html)
        self.assertLess(html.index("&lt;Seven&gt;"), html.index("Both"))
        self.assertLess(html.index("Both"), html.index("Five"))
        self.assertEqual(html.count("Both"), 1)
        self.assertIn('<td>EADRIATIC</td><td class="num">0</td><td class="num">7</td>', html)
        self.assertIn('<td>GT</td><td class="num">5</td><td class="num">0</td>', html)
        self.assertIn('<td class="num">6</td><td class="num">6</td>', html)

    def test_long_runs_empty_and_position(self):
        self.assertIn("No hay jugadores", render_long_current_runs({}))
        html = render_page({}, {}, [], payload())
        self.assertLess(html.index("<h2>Current Streaks"), html.index("<h2>Rachas actuales"))
        self.assertLess(html.index("<h2>Rachas actuales"), html.index("<h2>Coincident Matches"))

    def test_v2_is_the_only_current_streaks_block_and_has_the_final_name(self):
        html = render_page({}, {}, [], payload())
        self.assertEqual(html.count("<h2>Current Streaks — Last 8 Hours</h2>"), 1)
        self.assertNotIn("Current Streaks V2", html)
        self.assertNotIn("Current Streaks — Legacy", html)
        for header in ("PLAYER", "W", "D", "L", "PLAYED", "LAST 24"):
            self.assertIn(f"<th>{header}</th>", html)
        self.assertIn('<abbr title="Sin ganar">SG</abbr>', html)
        self.assertIn('<abbr title="Sin perder">SP</abbr>', html)
        self.assertNotIn("<th>STREAK</th>", html)

    def test_sequence_streak_balance_and_empty_payload(self):
        html = render_current_streaks_v2(payload())
        self.assertIn("VEDVVD", html)
        self.assertNotIn("D × 1", html)
        self.assertIn("🟢 Lucas", html)
        self.assertEqual(render_current_streaks_v2({}).count("Visible players: 0"), 2)

    def test_name_is_escaped(self):
        html = render_current_streaks_v2(payload([session(player="<Lucas>")]))
        self.assertIn("&lt;Lucas&gt;", html)
        self.assertNotIn("<Lucas>", html)

    def test_last_result_uses_madrid_date_and_handles_missing_time(self):
        for timestamp, expected in (
            ("2026-08-01T23:15:00Z", "02/08/2026 01:15 (Madrid)"),
            ("2026-01-01T23:15:00Z", "02/01/2026 00:15 (Madrid)"),
            (None, "Hora del último resultado no disponible"),
        ):
            with self.subTest(timestamp=timestamp):
                html = render_current_streaks_v2(payload([session(last_result_timestamp=timestamp)]))
                self.assertIn(expected, html)
                self.assertIn('<details class="player-result"><summary>', html)

    def test_current_unbeaten_and_winless_runs(self):
        for sequence, without_win, without_loss in (
            ("VEDDE", 4, 1), ("DEVVE", 1, 4),
            ("EEE", 3, 3), ("VVV", 0, 3), ("DDD", 3, 0),
            ("", 0, 0), ("V" + "E" * 30, 30, 31),
        ):
            with self.subTest(sequence=sequence):
                html = render_current_streaks_v2(payload([session(
                    sequence=sequence, last_24=sequence[-24:],
                )]))
                self.assertIn(
                    f'<td class="num">{without_win}</td>'
                    f'<td class="num">{without_loss}</td></tr>', html,
                )


if __name__ == "__main__":
    unittest.main()
