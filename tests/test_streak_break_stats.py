import unittest

from datetime import datetime, timedelta
from streak_break_stats import MADRID, historical_windows, summarize_windows
from web_tracker.streak_statistics import render_streak_statistics


def group_matches(start, prefix, league="GT"):
    rows = []
    for index, (a, b, minutes) in enumerate(((0, 1, 0), (2, 3, 0), (1, 2, 15),
                                            (0, 3, 75), (1, 2, 90), (0, 1, 470))):
        for player, rival, result in ((a, b, "V"), (b, a, "D")):
            rows.append({"league": league, "match_id": f"{prefix}{index}",
                         "player": f"{prefix}{player}", "player_key": f"{prefix}{player}",
                         "rival_key": f"{prefix}{rival}", "result": result,
                         "timestamp_utc": (start + timedelta(minutes=minutes)).isoformat()})
    return rows


class StreakBreakStatsTests(unittest.TestCase):
    def lookup(self, sequences, kind, length):
        return next(row["horizons"] for row in summarize_windows(sequences)
                    if row["kind"] == kind and row["length"] == length)

    def test_break_and_separate_horizon_denominators(self):
        horizons = self.lookup(["DDDDV", "DDDDE", "DDDD"], "SG", 4)
        self.assertEqual(horizons[1]["break_pct"], 50)
        self.assertEqual(horizons[1]["incomplete"], 1)
        self.assertEqual(horizons[3]["broken"], 1)
        self.assertEqual(horizons[3]["incomplete"], 2)

    def test_no_followup_across_windows(self):
        horizons = self.lookup(["DDDD", "V"], "SG", 4)
        self.assertIsNone(horizons[1]["break_pct"])
        self.assertEqual(horizons[1]["incomplete"], 1)

    def test_draw_extends_both_kinds_and_each_run_counts_once(self):
        for kind in ("SG", "SP"):
            horizons = self.lookup(["EEEEEE"], kind, 4)
            self.assertEqual(horizons[1]["continued"], 1)
            self.assertEqual(horizons[3]["incomplete"], 1)

    def test_new_run_after_break(self):
        horizons = self.lookup(["DDVDDV"], "SG", 2)
        self.assertEqual(horizons[1]["broken"], 2)

    def test_staggered_groups_midnight_and_duplicates(self):
        for league, hour, offset in (("GT", 21, 60), ("EADRIATIC", 23, 20)):
            start = datetime(2026, 9, 16, hour, tzinfo=MADRID)
            records = group_matches(start, "a", league)
            records += group_matches(start + timedelta(minutes=offset), "b", league)
            windows = historical_windows(records + records, start + timedelta(hours=12))
            self.assertEqual(len(windows), 8)
            a = next(w for w in windows if w["player_key"] == "a0")
            b = next(w for w in windows if w["player_key"] == "b0")
            self.assertEqual(a["sequence"], "VVV")
            self.assertEqual(a["stream"], 1)
            self.assertEqual(b["stream"], 2)
            self.assertNotEqual(a["start"], b["start"])

    def test_adjacent_turns_do_not_merge(self):
        start = datetime(2026, 9, 16, 5, tzinfo=MADRID)
        records = group_matches(start, "a")
        next_rows = group_matches(start + timedelta(hours=8), "a")
        for row in next_rows:
            row["match_id"] += "next"
        windows = historical_windows(records + next_rows, start + timedelta(hours=20))
        self.assertEqual(len([w for w in windows if w["player_key"] == "a0"]), 2)

    def test_unknown_start_is_excluded_and_future_not_used(self):
        start = datetime(2026, 9, 16, 5, tzinfo=MADRID)
        records = group_matches(start + timedelta(minutes=5), "a")
        self.assertEqual(historical_windows(records, start + timedelta(hours=12)), [])
        self.assertEqual(historical_windows(group_matches(start, "a"), start - timedelta(seconds=1)), [])

    def test_json_cannot_close_script(self):
        html = render_streak_statistics({"leagues": {}, "name": "</script><img>"})
        self.assertNotIn("</script><img>", html)
        self.assertIn("\\u003c/script>", html)


if __name__ == "__main__":
    unittest.main()
