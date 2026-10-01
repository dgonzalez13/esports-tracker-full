import unittest
from datetime import datetime, timezone

from tests.test_h2h_analysis import perspective
from web_tracker.generate_site import attach_recent_group_h2h, render_recent_group_h2h


class RecentGroupH2HTests(unittest.TestCase):
    def test_next_fixture_is_earliest_scheduled_pair_in_same_league(self):
        group = {"target": ["David", "Fox", "C"]}
        data = {"leagues": {"GT": {"groups": [group]}}}
        def fixture(index, stamp, **overrides):
            return dict(perspective(index, None, timestamp=stamp), fixture_status="scheduled", **overrides)
        schedule = {"sources": {"GT": {"records": [
            fixture(1, "2026-10-01T11:59:00Z"),
            fixture(2, "2026-10-01T14:00:00Z"),
            fixture(3, "2026-10-01T12:30:00Z"),
            dict(fixture(4, "2026-10-01T12:01:00Z"), fixture_status="unknown"),
            dict(fixture(5, "2026-10-01T12:02:00Z"), result="V", fixture_status="finished"),
        ]}, "EADRIATIC": {"records": [
            dict(fixture(6, "2026-10-01T12:05:00Z"), league="EADRIATIC")
        ]}}}
        attach_recent_group_h2h(data, [], datetime(2026, 10, 1, 12, tzinfo=timezone.utc), schedule)
        players = group["recent_h2h"]["players"]
        self.assertEqual(players[0]["rivals"][0]["next_match"], "2026-10-01T12:30:00+00:00")
        self.assertEqual(players[1]["rivals"][0]["next_match"], players[0]["rivals"][0]["next_match"])
        html = render_recent_group_h2h(group)
        self.assertIn("01/10 14:30", html)
        self.assertIn("Sin programar", html)
        self.assertLess(html.index("Secuencia (8h)"), html.index("Próximo partido (Madrid)"))

    def test_highlights_zero_wins_using_historical_percentage(self):
        rivals = [
            {"rival": str(pct), "played": 3, "wins": wins, "draws": 1,
             "losses": 2, "historical_win_pct": pct, "historical_played": 100,
             "sequence": "DED"}
            for pct, wins in [(36, 0), (35, 0), (30, 0), (29.99, 0), (40, 1)]
        ]
        html = render_recent_group_h2h({"recent_h2h": {
            "start": "start", "end": "end", "players": [{"player": "A", "rivals": rivals}]
        }})
        self.assertEqual(html.count('<tr class="recent-h2h-green">'), 1)
        self.assertEqual(html.count('<tr class="recent-h2h-blue">'), 2)

    def test_time_bounds_direction_league_and_empty_rivals(self):
        group = {"target": ["David", "Fox", "C", "D", "E"]}
        data = {"leagues": {"GT": {"groups": [group]}}}
        records = [
            perspective(1, "V", timestamp="2026-10-01T03:59:59Z"),
            perspective(2, "D", timestamp="2026-10-01T04:00:00Z"),
            perspective(3, "E", timestamp="2026-10-01T08:00:00Z"),
            perspective(4, "V", timestamp="2026-10-01T12:00:00Z"),
            perspective(5, "V", timestamp="2026-10-01T12:00:01Z"),
            perspective(6, "V", league="EADRIATIC", timestamp="2026-10-01T09:00:00Z"),
            perspective(7, "V", player="Fox", rival="David", timestamp="2026-10-01T04:00:00Z"),
        ]
        attach_recent_group_h2h(data, reversed(records), datetime(2026, 10, 1, 12, tzinfo=timezone.utc))
        players = group["recent_h2h"]["players"]
        self.assertEqual(len(players), 5)
        self.assertTrue(all(len(p["rivals"]) == 4 for p in players))
        row = players[0]["rivals"][0]
        self.assertEqual(row["sequence"], "DEV")
        self.assertEqual(row["played"], 3)
        self.assertEqual(row["win_pct"], 33.33)
        self.assertEqual(row["historical_win_pct"], 50.0)
        self.assertEqual(row["historical_played"], 4)
        self.assertEqual(players[1]["rivals"][0]["sequence"], "V")
        html = render_recent_group_h2h(group)
        self.assertIn("DEV", html)
        self.assertIn("Sin partidos", html)
        self.assertIn("V% (total)", html)
        self.assertIn("50.00%", html)
        self.assertNotIn("V% (8h)", html)


if __name__ == "__main__":
    unittest.main()
