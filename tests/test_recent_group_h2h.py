import unittest
from datetime import datetime, timezone

from tests.test_h2h_analysis import perspective
from web_tracker.generate_site import attach_recent_group_h2h, render_recent_group_h2h, render_page, render_recent_group_h2h_dashboard, recent_h2h_row_class


class RecentGroupH2HTests(unittest.TestCase):
    def test_highlighting_requires_more_than_twenty_historical_matches(self):
        row = {"wins": 0, "historical_win_pct": 45}
        for total in (0, 1, 19, 20):
            self.assertEqual(recent_h2h_row_class(dict(row, historical_played=total)), "")
        self.assertEqual(recent_h2h_row_class(dict(row, historical_played=21)), "recent-h2h-green")
    def test_minimum_gap_strict_boundary_and_configurable_cutoff(self):
        row = {"wins": 0, "historical_win_pct": 42, "historical_played": 100,
               "historical_wins": 42, "historical_losses": 55}
        self.assertEqual(recent_h2h_row_class(row), "")
        row["historical_losses"] = 52
        self.assertEqual(recent_h2h_row_class(row), "recent-h2h-green")
        self.assertEqual(recent_h2h_row_class(row, -5), "")
        row["historical_losses"] = 47
        self.assertEqual(recent_h2h_row_class(row, -5), "recent-h2h-green")
    def test_total_percentage_uses_existing_historical_matrix_not_partial_jsonl(self):
        group = {"target": ["Voodoo", "William"], "h2h_matrix": [
            {"player": "Voodoo", "rivals": [{"rival": "William", "matches": 289, "W": 90, "L": 154,
                                             "win_pct": 90 / 289 * 100}]}
        ]}
        data = {"leagues": {"GT": {"groups": [group]}}}
        records = [perspective(1, "V", player="Voodoo", rival="William", timestamp="2026-09-30T12:00:00Z"),
                   perspective(2, "D", player="Voodoo", rival="William", timestamp="2026-10-01T11:00:00Z")]
        attach_recent_group_h2h(data, records, datetime(2026, 10, 1, 12, tzinfo=timezone.utc))
        row = group["recent_h2h"]["players"][0]["rivals"][0]
        self.assertEqual(row["historical_played"], 289)
        self.assertEqual(row["historical_win_pct"], 90 / 289 * 100)
        self.assertEqual(row["sequence"], "D")
        self.assertEqual(row["played"], 1)
        html = render_recent_group_h2h(group)
        self.assertIn("31.14%", html)
        self.assertNotIn('<tr class="recent-h2h-blue">', html)
        self.assertNotIn('<tr class="recent-h2h-green">', html)

    def test_standalone_block_above_coincident_matches_without_duplicate(self):
        group = {"target": ["David", "Fox"], "label": "Grupo 1"}
        data = {"leagues": {"GT": {"groups": [group]}}}
        attach_recent_group_h2h(data, [], datetime(2026, 10, 1, 12, tzinfo=timezone.utc))
        html = render_page(data, {}, [])
        self.assertLess(html.index('id="recent-group-h2h"'), html.index('<h2>Coincident Matches'))
        self.assertEqual(html.count('Próximo partido'), 2)
        self.assertIn('No hay enfrentamientos destacados.', html)
        self.assertGreater(html.index('Frente a frente · últimas 8 horas'), html.index('<h2>Group Analysis'))

    def test_summary_filters_and_sorts_highlighted_rows_unknown_time_last(self):
        def rival(name, pct, wins=0, stamp=None):
            return {"rival": name, "wins": wins, "historical_win_pct": pct,
                    "played": 3, "sequence": "DED", "next_match": stamp, "historical_played": 100}
        group = {"label": "Grupo 1", "recent_h2h": {"players": [{"player": "A", "rivals": [
            rival("Unknown", 40), rival("Late", 36, stamp="2026-10-01T14:00:00Z"),
            rival("Early", 40, stamp="2026-10-01T12:00:00Z"),
            rival("FormerBlue", 35, stamp="2026-10-01T11:00:00Z"),
            rival("HasWin", 40, wins=1), rival("LowPct", 29),
        ]}]}}
        html = render_recent_group_h2h_dashboard({"leagues": {"GT": {"groups": [group]}}})
        self.assertLess(html.index('Early'), html.index('Late'))
        self.assertLess(html.index('Late'), html.index('Unknown'))
        self.assertNotIn('HasWin', html)
        self.assertNotIn('LowPct', html)
        self.assertNotIn('FormerBlue', html)
        self.assertEqual(html.count('<tr class="recent-h2h-green">'), 3)
        self.assertEqual(html.count('<tr class="recent-h2h-blue">'), 0)

    def test_next_fixture_is_earliest_scheduled_pair_in_same_league(self):
        group = {"target": ["David", "Fox", "C"]}
        data = {"leagues": {"GT": {"groups": [group]}}}
        def fixture(index, stamp, **overrides):
            return dict(perspective(index, None, timestamp=stamp), fixture_status="scheduled", **overrides)
        schedule = {"sources": {"GT": {"records": [
            dict(fixture(1, "2026-10-01T11:59:00Z"), fixture_status="finished", result="D"),
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
        self.assertLess(html.index("Secuencia (8h)"), html.index("Próximo partido"))

    def test_started_pending_fixture_overrides_future_and_finished_history_excludes_it(self):
        reference = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        group = {"target": ["David", "Fox"]}
        data = {"leagues": {"GT": {"groups": [group]}}}
        pending = dict(perspective(1, None, timestamp="2026-10-01T11:55:00Z"), fixture_status="unknown")
        future = dict(perspective(2, None, timestamp="2026-10-01T13:00:00Z"), fixture_status="scheduled")
        schedule = {"sources": {"GT": {"records": [pending, future]}}}
        attach_recent_group_h2h(data, [], reference, schedule)
        row = group["recent_h2h"]["players"][0]["rivals"][0]
        self.assertTrue(row["match_started"])
        self.assertIn("11:55", row["next_match"])
        self.assertIn("· Iniciado", render_recent_group_h2h(group))
        completed = dict(pending, result="D")
        attach_recent_group_h2h(data, [completed], reference, schedule)
        row = group["recent_h2h"]["players"][0]["rivals"][0]
        self.assertFalse(row["match_started"])
        self.assertIn("13:00", row["next_match"])

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
        self.assertEqual(html.count('<tr class="recent-h2h-blue">'), 0)

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
