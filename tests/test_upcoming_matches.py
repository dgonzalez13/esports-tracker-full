from datetime import datetime, timedelta, timezone
import unittest

from web_tracker.upcoming_matches import upcoming_fixtures, render_upcoming_matches, upcoming_with_estimates


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

    def test_estimates_appear_in_upcoming_list_and_expired_slots_do_not(self):
        pair = dict(player='David', rival='Fox', estimated_fixtures=[
            {'timestamp': (self.now + timedelta(minutes=m)).isoformat()} for m in (-5, 20, 95)])
        rows = upcoming_with_estimates({}, self.now, [pair, pair])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['estimated'] for row in rows))
        html = render_upcoming_matches({}, self.now, [pair])
        self.assertIn('David', html)
        self.assertIn('Fox', html)
        self.assertEqual(html.count('class="estimated-match-label"'), 2)
        self.assertIn('data-league="EADRIATIC"', html)
        self.assertNotIn('>13:55</time>', html)

    def test_official_pair_takes_priority_over_estimates(self):
        schedule = {'sources': {'EADRIATIC': {'records': [self.fixture(player='David', rival='Fox')]}}}
        pairs = [dict(player='Fox', rival='David', estimated_fixtures=[
            {'timestamp': (self.now + timedelta(minutes=75)).isoformat()}])]
        rows = upcoming_with_estimates(schedule, self.now, pairs)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].get('estimated'))

    def test_safe_names_updates_and_madrid_midnight(self):
        schedule = {"sources": {"GT": {"records": [self.fixture(
            player="<script>", timestamp_utc="2026-09-17T23:10:00Z")],
            "updated_at": self.now.isoformat(), "error": "failure"}}}
        html = render_upcoming_matches(schedule, self.now)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('title="18/09/2026 01:10 (Madrid)"', html)
        self.assertIn('>01:10</time>', html)
        self.assertIn("falló la última actualización", html)
        self.assertIn("EADRIATIC: sin actualización disponible", html)


if __name__ == "__main__":
    unittest.main()
