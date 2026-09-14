import unittest
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, Mock

import requests

from coincident_matches import CoincidentPairResults
from coincident_schedule import attach_schedules
from fixture_schedule import parse_gt_fixtures, fetch_gt_fixtures, refresh_schedule
from eadriatic_leagues import parse_history_records
from web_tracker.generate_site import _coincident_pair_metrics, render_coincident_pair


def event(player, minute, result=None):
    return {"league": "GT", "player": player, "player_key": player.lower(),
            "rival": "Opponent", "rival_key": "opponent", "result": result,
            "match_id": f"{player}-{minute}", "timestamp_utc": f"2026-09-14T10:{minute:02}:00Z"}


def pair():
    return {"player_a": "A", "player_b": "B", "player_a_league": "GT", "player_b_league": "GT",
            "player_a_indicator": "GREEN", "player_b_indicator": "GREEN",
            "max_gap_minutes": 30, "matches": []}


class CalendarTests(unittest.TestCase):
    def test_calendar_refresh_retains_old_source_on_failure(self):
        folder = Path(__file__).parent / ".tmp" / uuid4().hex
        folder.mkdir(parents=True)
        path = folder / "schedule.json"
        previous = {"updated_at": "2026-09-13T10:00:00Z", "records": [event("A", 30)]}
        path.write_text(json.dumps({"sources": {"GT": previous}}), encoding="utf-8")
        with patch("fixture_schedule.fetch_gt_fixtures", side_effect=requests.Timeout), \
             patch("fixture_schedule.fetch_eadriatic_html", return_value=""), \
             patch("fixture_schedule.parse_history_records", return_value=[]):
            payload = refresh_schedule(path)
        self.assertEqual(payload["sources"]["GT"]["records"], previous["records"])
        self.assertEqual(payload["sources"]["GT"]["updated_at"], previous["updated_at"])
        self.assertIn("error", payload["sources"]["GT"])
        self.assertTrue(payload["sources"]["GT"]["error"])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    def test_gt_calendar_paginates_without_filtering_out_future_statuses(self):
        page1, page2 = Mock(), Mock()
        page1.json.return_value = [{}] * 100
        page2.json.return_value = []
        with patch("fixture_schedule.requests.get", side_effect=[page1, page2]) as get:
            fetch_gt_fixtures(datetime(2026, 9, 14, tzinfo=timezone.utc))
        self.assertEqual([c.kwargs["params"]["offset"] for c in get.call_args_list], [0, 100])
        self.assertNotIn("status", get.call_args.kwargs["params"])
        self.assertTrue(get.call_args.kwargs["params"]["kickoff"].startswith("gte:"))

    def attach(self, events, value=None):
        pairs = CoincidentPairResults([value or pair()])
        attach_schedules(pairs, [], {"sources": {"GT": {"updated_at": "2026-09-14T10:35:00Z", "records": events}}},
                         datetime(2026, 9, 14, 10, 35, tzinfo=timezone.utc))
        return pairs[0]

    def test_break_pairs_latest_unused_and_unpaired_does_not_affect_statistics(self):
        value = self.attach([event("A", 0, "V"), event("B", 0, "V"), event("B", 15, "D"),
                             event("B", 30, "D"), event("A", 45)])
        self.assertEqual(len(value["matches"]), 1)
        row, = value["calendar_matches"]
        self.assertEqual((row["player_a_match_id"], row["player_b_match_id"]), ("A-45", "B-30"))
        self.assertEqual(row["state"], "Failed")
        self.assertEqual([r["match_id"] for r in value["unpaired_matches"]], ["B-15"])
        metrics = _coincident_pair_metrics(value, {})
        self.assertEqual(metrics["misses_since_hit"], 1)
        self.assertEqual(metrics["max_misses_without_hit"], 1)
        self.assertEqual(metrics["both_failed_since_hit"], 0)
        self.assertEqual(metrics["pending_second_result"], 1)
        html = render_coincident_pair(value, metrics)
        self.assertIn("Failed", html)
        self.assertIn("Scheduled", html)
        self.assertIn("Finished (D)", html)
        self.assertIn("Unpaired matches", html)

    def test_pending_pairs_are_not_misses_and_final_result_updates_double_failure(self):
        for result, misses, doubles in ((None, 0, 0), ("V", 0, 0), ("D", 1, 0)):
            value = self.attach([event("A", 30, result), event("B", 45)])
            metrics = _coincident_pair_metrics(value, {})
            self.assertEqual(metrics["misses_since_hit"], misses)
            self.assertEqual(metrics["both_failed_since_hit"], doubles)
        value = self.attach([event("A", 0, "D"), event("B", 15, "D")])
        self.assertEqual(_coincident_pair_metrics(value, {})["both_failed_since_hit"], 1)
        self.assertFalse(value["calendar_matches"])

    def test_future_results_do_not_change_pairing_and_duplicates_are_removed(self):
        events = [event("A", 0), event("B", 0), event("B", 15), event("B", 30), event("A", 45)]
        before = self.attach(events + events)
        after = self.attach([dict(e, result="D") for e in events])
        ids = lambda rows: [(r["player_a_match_id"], r["player_b_match_id"]) for r in rows]
        self.assertEqual(ids(before["calendar_matches"]), ids(after["matches"]))
        self.assertEqual(len(before["calendar_matches"]), 2)

    def test_every_pair_has_its_own_calendar_including_cross_league_custom_pairs(self):
        automatic = pair()
        custom = dict(pair(), player_a="C", player_a_league="EADRIATIC")
        pairs = CoincidentPairResults([automatic], custom_pairs=[custom])
        schedule = {"sources": {
            "GT": {"records": [event("A", 45), event("B", 30)]},
            "EADRIATIC": {"records": [dict(event("C", 45), league="EADRIATIC")]},
        }}
        attach_schedules(pairs, [], schedule, datetime(2026, 9, 14, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(automatic["calendar_matches"][0]["player_b_match_id"], "B-30")
        self.assertEqual(custom["calendar_matches"][0]["player_b_match_id"], "B-30")
        self.assertEqual(set(custom["calendar_sources"]), {"GT", "EADRIATIC"})

    def test_missing_calendar_preserves_history_and_warns(self):
        value = pair()
        value["matches"] = [{"pair_order": 1, "confirmation": "BOTH_GREEN"}]
        attach_schedules([value], [], {}, datetime.now(timezone.utc))
        self.assertEqual(len(value["matches"]), 1)
        self.assertIn("Unavailable", render_coincident_pair(value))

    def test_red_signal_draw_and_excluded_opponent(self):
        value = pair()
        value["player_a_indicator"] = "RED"
        value = self.attach([event("A", 30, "E"), event("B", 45)], value)
        self.assertEqual(value["calendar_matches"][0]["state"], "Failed")
        schedule = {"sources": {"GT": {"records": [event("A", 30), event("B", 45)]}}}
        attach_schedules([value], [], schedule, datetime(2026, 9, 14, 10, tzinfo=timezone.utc), {("GT", "opponent")})
        self.assertFalse(value["calendar_matches"])
        self.assertFalse(value["unpaired_matches"])

    def test_gt_pending_and_provisional_scores_are_not_final_results(self):
        match = {"id": 1, "kickoff": "2026-09-14T10:00:00Z", "status": 0,
                 "participants": [{"side": side, "participant": {"player": {"nickname": player}}}
                                  for side, player in (("home", "A"), ("away", "B"))],
                 "result": {"stats": {"home_score": 2, "away_score": 1}}}
        for status in (0, 1, 2, 4):
            match["status"] = status
            self.assertTrue(all(r["result"] is None for r in parse_gt_fixtures([match])))
        match["status"] = 3
        self.assertEqual([r["result"] for r in parse_gt_fixtures([match])], ["V", "D"])

    def test_ead_pending_is_calendar_only_and_midnight_is_resolved(self):
        html = '''<span class="fg-heading">FC26 R1(TEST)14.09.2026</span>
        <span class="time-heading">23:45</span><table>
        <tr data-match-href="/match/1.html"><td>Team (A)</td><td>2 - 1</td><td>Team (B)</td></tr></table>
        <span class="fg-heading">FC26 R2(TEST)15.09.2026</span>
        <span class="time-heading">00:15</span><table>
        <tr data-match-href="/match/2.html"><td>Team (A)</td><td>VS</td><td>Team (B)</td></tr></table>'''
        self.assertEqual(len(parse_history_records(html, "test")), 2)
        records = parse_history_records(html, "test", include_scheduled=True)
        self.assertEqual(len(records), 4)
        self.assertIsNone(records[-1]["result"])
        self.assertEqual(records[-1]["timestamp_utc"], "2026-09-14T22:15Z")


if __name__ == "__main__":
    unittest.main()
