import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from update_tracked_players import (
    FixtureGroup, parse_eadriatic_fixture_groups, parse_gt_fixture_groups,
    rewrite_tracked_players, select_fixture_group, target_start,
)


class TargetSelectionTests(unittest.TestCase):
    def test_each_stream_resolves_current_and_next_independently(self):
        now = datetime(2026, 8, 29, 5, 10, tzinfo=timezone.utc)  # 07:10 Madrid
        self.assertEqual(target_start("EADRIATIC", 1, "C", now).strftime("%H:%M"), "07:00")
        self.assertEqual(target_start("EADRIATIC", 1, "N", now).strftime("%H:%M"), "15:00")
        self.assertEqual(target_start("EADRIATIC", 2, "C", now).strftime("%H:%M"), "23:20")
        self.assertEqual(target_start("EADRIATIC", 2, "N", now).strftime("%H:%M"), "07:20")
        self.assertEqual(target_start("GT", 1, "C", now).strftime("%H:%M"), "05:00")
        self.assertEqual(target_start("GT", 2, "N", now).strftime("%H:%M"), "14:00")

    def test_nearest_complete_group_must_be_close_to_target(self):
        target = datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc)
        group = FixtureGroup(target, ("A", "B", "C", "D", "E"), "x")
        self.assertEqual(select_fixture_group([group], target), group)
        with self.assertRaises(RuntimeError):
            select_fixture_group([group], target.replace(hour=9))


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
