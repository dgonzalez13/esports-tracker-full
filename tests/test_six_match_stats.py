import unittest
from datetime import datetime, timedelta, timezone
from six_match_stats import calculate_six_match_stats
from tests.test_h2h_analysis import perspective
from web_tracker.generate_site import render_six_match_stats


class SixMatchTests(unittest.TestCase):
    def test_first_four_five_six_use_prefix_not_later_victories(self):
        reference = datetime(2026, 9, 3, tzinfo=timezone.utc)
        for sequence, expected in [("DDDDVD", [0, 100, 100]), ("DDDDDV", [0, 0, 100]),
                                   ("DDDVDD", [100, 100, 100])]:
            result = calculate_six_match_stats(self.history(sequence=sequence), reference)
            rows = [r for r in result["horizons"] if r["threshold"] == 40]
            self.assertEqual([r["win_pct"] for r in rows], expected)
            self.assertTrue(all(r["sample"] == 1 for r in rows))
            self.assertEqual([r["without_win_pct"] for r in rows], [100 - v for v in expected])
            self.assertIn("primeros 4, 5 o 6 partidos", render_six_match_stats(result))

    def history(self, wins=9, sequence="DEDEDD"):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        records = [perspective(i, "V" if i < wins else "D",
                               timestamp=(start + timedelta(minutes=i)).isoformat()) for i in range(20)]
        records += [perspective(20+i, result, timestamp=(start + timedelta(days=1, minutes=i)).isoformat())
                    for i, result in enumerate(sequence)]
        return records

    def row(self, payload, threshold, k):
        return next(r for r in payload["rows"] if r["threshold"] == threshold and r["initial_without_win"] == k)

    def test_all_six_conditions_deduplicated_no_future_leakage(self):
        records = self.history()
        result = calculate_six_match_stats(records + records, datetime(2026, 9, 3, tzinfo=timezone.utc))
        self.assertEqual(result["complete_series"], 1)
        for threshold in (35, 40):
            for k in range(6):
                row = self.row(result, threshold, k)
                self.assertEqual((row["sample"], row["zero_wins"], row["remaining_win_pct"]), (1, 1, 0))

    def test_strict_threshold_and_conditional_denominator(self):
        result = calculate_six_match_stats(self.history(8, "DEVDDD"), datetime(2026, 9, 3, tzinfo=timezone.utc))
        self.assertEqual(self.row(result, 40, 0)["sample"], 0)
        for k in (0, 1, 2):
            row = self.row(result, 35, k)
            self.assertEqual((row["sample"], row["remaining_win_pct"]), (1, 100))
        self.assertEqual(self.row(result, 35, 3)["sample"], 0)
        self.assertIn("Sin muestra", render_six_match_stats(result))

    def test_open_and_incomplete_series_excluded(self):
        records = self.history()
        reference = datetime(2026, 9, 2, 0, 20, tzinfo=timezone.utc)
        self.assertEqual(calculate_six_match_stats(records, reference)["complete_series"], 0)
        self.assertEqual(calculate_six_match_stats(records[:-1], datetime(2026, 9, 3, tzinfo=timezone.utc))["complete_series"], 0)


if __name__ == "__main__":
    unittest.main()
