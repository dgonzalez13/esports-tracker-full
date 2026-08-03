import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

import group_analysis
from coincident_matches import calculate_all_coincident_pairs
from current_streaks_v2 import calculate_operational_snapshot
from match_history import name_key
from selected_players import is_operational_record, parse_tracked_player_line
from web_tracker.generate_site import load_current_streaks
import web_tracker.generate_site as site


def event(player, rival, result="V", minute=0, league="GT", timestamp=None):
    stamp = datetime(2026, 8, 3, 10, tzinfo=timezone.utc) + timedelta(minutes=minute)
    timestamp = timestamp or stamp.isoformat().replace("+00:00", "Z")
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "rival": rival, "rival_key": name_key(rival), "result": result,
        "timestamp_utc": timestamp,
        "match_id": f"{league}:{player}:{minute}",
        "perspective_id": f"{league}:{player}:{minute}:{name_key(player)}",
    }


def tracked(player, league="GT", excluded=False):
    return parse_tracked_player_line(f"{league}|{player}{'*' if excluded else ''}")


class CommonFilterTests(unittest.TestCase):
    def test_all_identity_combinations_leagues_unicode_and_empty_set(self):
        excluded = {("GT", name_key("Fóx")), ("EADRIATIC", name_key("Only Here"))}
        self.assertTrue(is_operational_record(event("Lucas", "Normal"), excluded))
        self.assertFalse(is_operational_record(event("Fóx", "Normal"), excluded))
        self.assertFalse(is_operational_record(event("Lucas", "Fo\u0301x"), excluded))
        self.assertFalse(is_operational_record(event("Fóx", "Fóx"), excluded))
        self.assertTrue(is_operational_record(event("Fóx", "Normal", league="EADRIATIC"), excluded))
        self.assertTrue(is_operational_record(event("Only Here", "Normal", league="GT"), excluded))
        self.assertFalse(is_operational_record(event("Only Here", "Normal", league="EADRIATIC"), excluded))
        self.assertTrue(is_operational_record(event("Lucas", "Normal"), set()))

    def test_invalid_keys_and_immutability(self):
        row = event("Lucas", "Fox")
        original = copy.deepcopy(row)
        self.assertFalse(is_operational_record({**row, "player_key": ""}, set()))
        self.assertFalse(is_operational_record({**row, "rival_key": ""}, set()))
        self.assertFalse(is_operational_record({**row, "league": ""}, set()))
        self.assertFalse(is_operational_record(None, set()))
        self.assertTrue(is_operational_record(row, {("EADRIATIC", "lucas")}))
        self.assertEqual(row, original)


class OperationalConsumersTests(unittest.TestCase):
    def setUp(self):
        self.players = [tracked("Lucas"), tracked("Fox", excluded=True), tracked("Kratos")]
        self.excluded = {("GT", "fox")}
        self.now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)

    def test_v2_recalculates_every_metric_and_minimum(self):
        rows = [
            event("Lucas", "Normal", "V", 0), event("Lucas", "Normal", "E", 10),
            event("Lucas", "Normal", "D", 20), event("Lucas", "Normal", "D", 30),
            event("Lucas", "Fox", "V", 40), event("Lucas", "Fox", "V", 50),
        ]
        snapshot = calculate_operational_snapshot(
            rows, self.players, reference_time=self.now, excluded_keys=self.excluded,
        )
        lucas = snapshot[0]
        self.assertEqual((lucas["played"], lucas["wins"], lucas["draws"], lucas["losses"]), (4, 1, 1, 2))
        self.assertEqual((lucas["sequence"], lucas["last_10"], lucas["current_streak"]), ("VEDD", "VEDD", 2))
        self.assertEqual((lucas["win_pct"], lucas["loss_pct"], lucas["indicator"]), (25.0, 50.0, "RED"))

    def test_coincident_discards_both_sides_and_preserves_remaining_pair(self):
        rows = [
            event("Lucas", "Fox", minute=0), event("Kratos", "Normal", minute=1),
            event("Lucas", "Normal", minute=10), event("Kratos", "Normal", minute=11),
        ]
        refs = [
            {"league": "GT", "player": "Lucas", "player_key": "lucas"},
            {"league": "GT", "player": "Kratos", "player_key": "kratos"},
        ]
        pairs = calculate_all_coincident_pairs(rows, refs, excluded_keys=self.excluded)
        self.assertEqual(len(pairs[0]["matches"]), 1)
        self.assertEqual(pairs[0]["matches"][0]["player_a_rival"], "Normal")

    def test_h2h_discards_excluded_principal_and_rival(self):
        rival = lambda name: {"rival": name, "W": 12, "D": 0, "L": 8, "matches": 20,
                              "win_pct": 60.0, "draw_pct": 0.0, "loss_pct": 40.0}
        result = {"league": "GT", "groups": [{"group_id": "g", "label": "g", "h2h_matrix": [
            {"player": "Lucas", "rivals": [rival("Fox"), rival("Kratos")]},
            {"player": "Fox", "rivals": [rival("Lucas")]},
        ]}]}
        alerts = group_analysis.calculate_h2h_alerts(
            result, [], {("GT", "lucas"), ("GT", "kratos")}, self.excluded,
        )
        self.assertEqual([(row["player"], row["rival"]) for row in alerts], [("Lucas", "Kratos")])

    def test_legacy_tracked_row_is_rebuilt_without_excluded_matches(self):
        rows = [event("Lucas", "Normal", "D", 0), event("Lucas", "Fox", "V", 1)]
        legacy = load_current_streaks(self.players, rows)
        lucas = next(row for row in legacy["GT"]["rows"] if row["player"] == "Lucas")
        self.assertEqual((lucas["W"], lucas["D"], lucas["L"], lucas["played"], lucas["seq"]), (0, 0, 1, 1, "D"))
        self.assertIn("match_history.jsonl", legacy["GT"]["source"])


class LegacyDailyScopeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / ".tmp" / f"task011-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        self.root = root
        self.gt = root / "gt"
        self.ead = root / "ead"
        self.gt.mkdir()
        self.ead.mkdir()
        (self.gt / "20260803_player_stats.txt").write_text(
            "player W D L played stk seq\n"
            "Lucas 9 0 0 9 9 VVVVVVVVV\n"
            "Kratos 0 0 9 9 9 DDDDDDDDD\n"
            "Untracked 2 0 1 3 0 VVD\n\n",
            encoding="utf-8",
        )
        (self.ead / "20260803_eadriatic_player_stats.txt").write_text(
            "player W D L played stk seq\nOther 1 0 0 1 1 V\n\n",
            encoding="utf-8",
        )
        self.leagues = {
            "GT": {"title": "GT League", "data_dir": self.gt},
            "EADRIATIC": {"title": "Eadriatic League", "data_dir": self.ead},
        }
        self.players = [tracked("Lucas"), tracked("Kratos")]

    def tearDown(self):
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self.root.rmdir()

    def test_local_day_boundaries_two_dates_balances_and_untracked_txt(self):
        records = [
            event("Lucas", "Normal", "D", timestamp="2026-08-02T21:59:59Z"),
            event("Lucas", "Normal", "V", timestamp="2026-08-02T22:00:00Z"),
            event("Lucas", "Normal", "E", timestamp="2026-08-03T21:59:59Z"),
            event("Lucas", "Normal", "D", timestamp="2026-08-03T22:00:00Z"),
            event("Kratos", "Normal", "D", timestamp="2026-08-03T08:00:00Z"),
            event("Kratos", "Normal", "D", timestamp="2026-08-03T09:00:00Z"),
        ]
        with patch.object(site, "LEAGUES", self.leagues):
            payload = load_current_streaks(self.players, records)
        rows = {row["player"]: row for row in payload["GT"]["rows"]}
        self.assertEqual((rows["Lucas"]["seq"], rows["Lucas"]["played"]), ("VE", 2))
        self.assertEqual(rows["Lucas"]["balance"], "🟢")
        self.assertEqual(rows["Kratos"]["balance"], "🔴")
        self.assertEqual(
            (rows["Untracked"]["W"], rows["Untracked"]["D"], rows["Untracked"]["L"], rows["Untracked"]["seq"]),
            (2, 0, 1, "VVD"),
        )

    def test_legacy_daily_and_v2_eight_hour_scopes_can_differ(self):
        records = [
            event("Lucas", "Normal", "V", timestamp="2026-08-02T22:00:00Z"),
            event("Lucas", "Normal", "D", timestamp="2026-08-03T20:00:00Z"),
        ]
        with patch.object(site, "LEAGUES", self.leagues):
            legacy = load_current_streaks(self.players, records)
        snapshot = calculate_operational_snapshot(
            records, self.players,
            reference_time=datetime(2026, 8, 3, 21, tzinfo=timezone.utc),
        )
        lucas_legacy = next(row for row in legacy["GT"]["rows"] if row["player"] == "Lucas")
        lucas_v2 = next(row for row in snapshot if row["player"] == "Lucas")
        self.assertEqual((lucas_legacy["played"], lucas_v2["played"]), (2, 1))

    def test_invalid_txt_date_keeps_daily_fallback_and_does_not_load_jsonl(self):
        dated = self.gt / "20260803_player_stats.txt"
        dated.rename(self.gt / "latest_player_stats.txt")
        with patch.object(site, "LEAGUES", self.leagues), patch.object(
            site, "load_all_history"
        ) as load_history:
            payload = load_current_streaks(self.players, [event("Lucas", "Normal")])
        load_history.assert_not_called()
        lucas = next(row for row in payload["GT"]["rows"] if row["player"] == "Lucas")
        self.assertEqual((lucas["played"], lucas["seq"]), (9, "VVVVVVVVV"))
        self.assertIn("Fallback", payload["GT"]["scope_note"])


if __name__ == "__main__":
    unittest.main()
