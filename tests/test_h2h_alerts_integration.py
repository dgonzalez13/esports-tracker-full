import copy
import sys
import unittest
from unittest.mock import patch

import group_analysis
from match_history import name_key


def perspective(index, result, league="GT", player="David", rival="Fox"):
    timestamp = f"2026-07-{index:02d}T08:00:00Z"
    match_id = f"{league.lower()}:{index:02d}:{player}:{rival}"
    return {
        "league": league, "player": player, "player_key": name_key(player),
        "rival": rival, "rival_key": name_key(rival), "result": result,
        "timestamp_utc": timestamp, "timestamp": timestamp,
        "match_id": match_id, "perspective_id": f"{match_id}:{name_key(player)}",
    }


def legacy_result(win_pct=60.0, matches=50, league="GT"):
    wins = round(matches * win_pct / 100)
    rival = {
        "rival": "Fox", "W": wins, "D": 5, "L": matches - wins - 5,
        "matches": matches, "win_pct": win_pct, "draw_pct": 10.0,
        "loss_pct": 100.0 - win_pct - 10.0, "seq": "legacy",
        "last5": "VVVED", "last10": "VVVEDDVVVE", "stk_win": 2,
        "stk_lose": 3,
    }
    return {"league": league, "groups": [{
        "group_id": "G1", "label": "Group 1",
        "h2h_matrix": [{"player": "David", "rivals": [rival]}],
    }]}


class H2HAlertIntegrationTests(unittest.TestCase):
    def test_complete_window_is_chronological_and_preserves_legacy(self):
        sequence = "VVVVVVVVVVVVEEEDDDDD"
        records = [perspective(i, result) for i, result in enumerate(sequence, 1)]
        original = copy.deepcopy(records)
        alert = group_analysis.calculate_h2h_alerts(legacy_result(), records)[0]

        self.assertEqual(alert["recent_sequence"], sequence)
        self.assertEqual((alert["recent_wins"], alert["recent_draws"], alert["recent_losses"]), (12, 3, 5))
        self.assertEqual(alert["recent_win_pct"], 60.0)
        self.assertEqual(alert["recent_win_pct_delta"], 0.0)
        self.assertEqual(alert["recent_trend"], "STABLE")
        self.assertEqual(alert["recent_sample_status"], "COMPLETE")
        self.assertTrue(alert["recent_window_complete"])
        self.assertEqual(alert["recent_available"], 20)
        self.assertEqual(alert["recent_window"], 20)
        self.assertEqual((alert["W"], alert["matches"], alert["win_pct"]), (30, 50, 60.0))
        self.assertEqual(alert["last10"], "VVVEDDVVVE")
        self.assertEqual(records, original)

    def test_partial_up_down_and_empty_samples(self):
        up = group_analysis.calculate_h2h_alerts(
            legacy_result(50.0), [perspective(i, "V") for i in range(1, 9)]
        )[0]
        down = group_analysis.calculate_h2h_alerts(
            legacy_result(60.0), [perspective(i, "D") for i in range(1, 9)]
        )[0]
        empty = group_analysis.calculate_h2h_alerts(legacy_result(), [
            perspective(1, "V", rival="Other"),
        ])[0]
        self.assertEqual((up["recent_trend"], up["recent_sample_status"]), ("UP", "LOW_SAMPLE"))
        self.assertEqual((up["recent_available"], up["recent_win_pct_delta"]), (8, 50.0))
        self.assertEqual(down["recent_trend"], "DOWN")
        self.assertEqual(empty["recent_available"], 0)
        self.assertEqual(empty["recent_sequence"], "")
        self.assertEqual(empty["recent_win_pct"], 0.0)
        self.assertEqual(empty["recent_win_pct_delta"], 0.0)
        self.assertIsNone(empty["recent_trend"])
        self.assertEqual(empty["recent_sample_status"], "EMPTY")
        self.assertFalse(empty["recent_window_complete"])

    def test_leagues_and_rivals_are_isolated(self):
        records = [
            perspective(1, "V", "GT"), perspective(2, "D", "EADRIATIC"),
            perspective(3, "D", "GT", rival="Other"),
        ]
        gt = group_analysis.calculate_h2h_alerts(legacy_result(league="GT"), records)[0]
        ead = group_analysis.calculate_h2h_alerts(legacy_result(league="EADRIATIC"), records)[0]
        self.assertEqual(gt["recent_sequence"], "V")
        self.assertEqual(ead["recent_sequence"], "D")

    def test_historical_threshold_and_signal_are_unchanged(self):
        self.assertEqual(group_analysis.calculate_h2h_alerts(legacy_result(47.99)), [])
        watch = group_analysis.calculate_h2h_alerts(legacy_result(48.0))[0]
        strong = group_analysis.calculate_h2h_alerts(legacy_result(50.0))[0]
        self.assertEqual(watch["signal"], "WATCH")
        self.assertEqual(strong["signal"], "STRONG")

    def test_output_is_deterministic(self):
        result = legacy_result()
        records = [perspective(1, "V")]
        self.assertEqual(
            group_analysis.calculate_h2h_alerts(result, records),
            group_analysis.calculate_h2h_alerts(result, records),
        )

    @patch.object(group_analysis, "render_result")
    @patch.object(group_analysis, "write_json")
    @patch.object(group_analysis, "analyze_league")
    @patch.object(group_analysis, "load_groups", return_value={})
    @patch.object(group_analysis, "load_all_history", return_value=[])
    def test_main_loads_normalized_history_once(self, load_history, _groups, analyze, write, _render):
        analyze.side_effect = lambda league, groups: {"league": league, "groups": []}
        with patch.object(sys, "argv", ["group_analysis.py", "ALL"]):
            group_analysis.main()
        load_history.assert_called_once_with()
        self.assertIs(write.call_args.args[2], load_history.return_value)


if __name__ == "__main__":
    unittest.main()
