import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from update_tracked_players import (
    FixtureGroup, parse_eadriatic_fixture_groups, parse_gt_fixture_groups,
    gt_target_start, rewrite_tracked_players, select_gt_group, select_stream_group,
)


class StreamSelectionTests(unittest.TestCase):
    """Both leagues run two interleaved five-player streams back to back rather
    than on a fixed daily clock, so selection is based on chronological
    alternation (stream 1, 2, 1, 2, ...), not an assumed hour-of-day grid."""

    def _groups(self, count=6, start_hour=6):
        base = datetime(2026, 8, 29, start_hour, tzinfo=timezone.utc)
        return [
            FixtureGroup(
                base + timedelta(hours=i),
                (f"P{i}a", f"P{i}b", f"P{i}c", f"P{i}d", f"P{i}e"),
                f"g{i}",
            )
            for i in range(count)
        ]

    def test_selects_alternating_streams_for_current_and_next(self):
        groups = self._groups()
        reference = groups[2].start_local + timedelta(minutes=30)
        self.assertEqual(select_stream_group(groups, 1, "C", reference).source_id, "g2")
        self.assertEqual(select_stream_group(groups, 2, "C", reference).source_id, "g1")
        self.assertEqual(select_stream_group(groups, 1, "N", reference).source_id, "g4")
        self.assertEqual(select_stream_group(groups, 2, "N", reference).source_id, "g3")

    def test_raises_when_no_group_available_on_requested_side(self):
        groups = self._groups()
        reference = groups[0].start_local - timedelta(hours=1)
        with self.assertRaises(RuntimeError):
            select_stream_group(groups, 1, "C", reference)
        with self.assertRaises(RuntimeError):
            select_stream_group(groups, 2, "C", reference)


class GTSelectionTests(unittest.TestCase):
    def test_current_and_next_follow_the_two_fixed_gt_schedules(self):
        reference = datetime(2026, 9, 2, 5, 30, tzinfo=timezone.utc)  # 07:30 Madrid
        self.assertEqual(gt_target_start(1, "C", reference).strftime("%d %H:%M"), "02 05:00")
        self.assertEqual(gt_target_start(1, "N", reference).strftime("%d %H:%M"), "02 13:00")
        self.assertEqual(gt_target_start(2, "C", reference).strftime("%d %H:%M"), "02 06:00")
        self.assertEqual(gt_target_start(2, "N", reference).strftime("%d %H:%M"), "02 14:00")

    def test_before_six_group_two_current_is_previous_day_at_22(self):
        reference = datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc)  # 05:30 Madrid
        self.assertEqual(gt_target_start(2, "C", reference).strftime("%d %H:%M"), "01 22:00")
        self.assertEqual(gt_target_start(2, "N", reference).strftime("%d %H:%M"), "02 06:00")

    def test_selects_nearest_scheduled_group_not_chronological_parity(self):
        target = datetime(2026, 9, 2, 13, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        groups = [
            FixtureGroup(target - timedelta(hours=1), ("X1", "X2", "X3", "X4", "X5"), "noise"),
            FixtureGroup(target, ("A", "B", "C", "D", "E"), "expected"),
            FixtureGroup(target + timedelta(hours=1), ("Y1", "Y2", "Y3", "Y4", "Y5"), "noise-2"),
        ]
        self.assertEqual(select_gt_group(groups, target).source_id, "expected")


class ParserTests(unittest.TestCase):
    def test_gt_groups_fixtures_by_season_and_requires_five_players(self):
        fixtures = []
        names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        for index, (a, b) in enumerate(zip(names, names[1:] + names[:1])):
            fixtures.append({
                "seasonId": 42,
                "kickoff": f"2026-08-29T03:{index * 5:02d}:00Z",
                "participants": [
                    {"participant": {"player": {"nickname": a}}},
                    {"participant": {"player": {"nickname": b}}},
                ],
            })
        groups = parse_gt_fixture_groups(fixtures)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0].players), set(names))
        self.assertEqual(groups[0].start_local.strftime("%H:%M"), "05:00")

    def test_eadriatic_extracts_five_players_without_results(self):
        rows = "".join(
            f'<tr data-match-href="/{i}"><td>Team ({a})</td><td>-</td><td>Team ({b})</td></tr>'
            for i, (a, b) in enumerate([
                ("Alpha", "Beta"), ("Gamma", "Delta"), ("Epsilon", "Alpha")
            ])
        )
        html = (
            '<span class="fg-heading">FC26 R1(TEST)29.08.2026</span>'
            '<span class="time-heading">07:00</span><table>' + rows + '</table>'
        )
        groups = parse_eadriatic_fixture_groups(html, datetime(2026, 8, 29, tzinfo=timezone.utc))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].players, ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"))


class RewriteTests(unittest.TestCase):
    def temp_path(self):
        return Path(__file__).parent / ".tmp" / f"tracked-{uuid.uuid4().hex}.txt"

    def test_replaces_four_blocks_and_preserves_directives_and_matching_star(self):
        path = self.temp_path()
        try:
            old = [f"EADRIATIC|E{i}" for i in range(1, 11)] + [f"GT|G{i}" for i in range(1, 10)] + ["GT|Keep*"]
            path.write_text("\n".join(old) + "\n\n@COINCIDENT_SELECT||GT|Keep\n@COINCIDENT_EXCLUDE||\n", encoding="utf-8")
            replacements = {
                ("EADRIATIC", 1): tuple(f"EA{i}" for i in range(1, 6)),
                ("EADRIATIC", 2): tuple(f"EB{i}" for i in range(1, 6)),
                ("GT", 1): tuple(f"GA{i}" for i in range(1, 6)),
                ("GT", 2): ("GB1", "GB2", "GB3", "GB4", "Keep"),
            }
            rewrite_tracked_players(path, replacements)
            value = path.read_text(encoding="utf-8")
            self.assertIn("GT|Keep*", value)
            self.assertIn("@COINCIDENT_SELECT||GT|Keep", value)
            self.assertEqual(len([line for line in value.splitlines() if line.startswith(("GT|", "EADRIATIC|"))]), 20)
        finally:
            path.unlink(missing_ok=True)

    def test_refuses_incomplete_or_duplicate_groups_without_writing(self):
        path = self.temp_path()
        try:
            original = "\n".join([f"EADRIATIC|E{i}" for i in range(10)] + [f"GT|G{i}" for i in range(10)]) + "\n"
            path.write_text(original, encoding="utf-8")
            with self.assertRaises(RuntimeError):
                rewrite_tracked_players(path, {("GT", 1): ("A", "A", "B", "C", "D")})
            self.assertEqual(path.read_text(encoding="utf-8"), original)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
