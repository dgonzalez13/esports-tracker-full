from datetime import datetime, timedelta, timezone
import unittest

from web_tracker.upcoming_matches import upcoming_fixtures, render_upcoming_matches


class UpcomingMatchesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    def fixture(self, minutes=10, **changes):
        row = dict(match_id="one", player="Untracked", rival="Opponent",
                   timestamp_utc=(self.now + timedelta(minutes=minutes)).isoformat(),
                   fixture_status="scheduled", result=None)
        row.update(changes)
        return row

    def test_deduplication_status_order_and_all_players(self):
        schedule = {"sources": {"GT": {"records": [
            self.fixture(90, match_id="two"), self.fixture(),
            self.fixture(player="Opponent", rival="Untracked"),
            self.fixture(-1, match_id="past"),
            self.fixture(match_id="final", fixture_status="finished"),
            self.fixture(match_id="unknown", fixture_status="unknown"),
            self.fixture(match_id="invalid", timestamp_utc="bad"),
        ]}, "EADRIATIC": {"records": [self.fixture(30)]}}}
        rows = upcoming_fixtures(schedule, self.now)
        self.assertEqual([row["league"] for row in rows], ["GT", "EADRIATIC", "GT"])
        self.assertEqual(rows[0]["player"], "Untracked")

    def test_safe_names_updates_and_madrid_midnight(self):
        schedule = {"sources": {"GT": {"records": [self.fixture(
            player="<script>", timestamp_utc="2026-09-17T23:10:00Z")],
            "updated_at": self.now.isoformat(), "error": "failure"}}}
        html = render_upcoming_matches(schedule, self.now)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("18/09 01:10", html)
        self.assertIn("falló la última actualización", html)
        self.assertIn("EADRIATIC: sin actualización disponible", html)


if __name__ == "__main__":
    unittest.main()
