import unittest
from datetime import datetime, timezone
from team_analysis import calculate_team_stats
from gtleagues_api import build_history_records
from fixture_schedule import parse_gt_fixtures
from eadriatic_leagues import parse_history_records
from match_history import merge_records
from tests.test_match_history import gt_match, EAD_HTML
from web_tracker.generate_site import render_team_statistics


class TeamTests(unittest.TestCase):
    def test_gt_perspectives_and_missing_teams_remain_compatible(self):
        fixture = gt_match()
        for participant, name, identity in zip(fixture['participants'], ['Madrid', 'Barcelona'], [17, 20]):
            participant['participant']['team'] = dict(name=name, id=identity)
        rows = build_history_records([fixture], 'sample')
        self.assertEqual(rows[0]['player_team'], 'Madrid')
        self.assertEqual(rows[1]['rival_team'], 'Madrid')
        self.assertEqual(rows[1]['player_team_id'], 20)
        old = [{k: v for k, v in r.items() if 'team' not in k} for r in rows]
        enriched = merge_records(old, rows)
        self.assertEqual(next(r for r in enriched if r['home_away'] == 'home')['player_team'], 'Madrid')
        fixture['status'] = 0
        scheduled = parse_gt_fixtures([fixture])
        self.assertEqual(scheduled[0]['player_team'], 'Madrid')
        self.assertIsNone(scheduled[0]['result'])

    def test_ead_teams_and_directional_stats_ignore_old_and_pending(self):
        records = parse_history_records(EAD_HTML, 'sample', include_scheduled=True)
        self.assertEqual(records[0]['player_team'], 'England')
        self.assertEqual(records[1]['player_team'], 'Belgium')
        reference = datetime(2026, 7, 15, tzinfo=timezone.utc)
        result = calculate_team_stats(records + records, reference)
        self.assertEqual(sum(r['played'] for r in result), 4)
        dexter = next(r for r in result if r['player'] == 'Dexter')
        self.assertEqual(dexter['wins_pct'], 100)
        eric = next(r for r in result if r['player'] == 'Eric')
        self.assertEqual(eric['losses_pct'], 100)
        self.assertEqual(calculate_team_stats([{k:v for k,v in r.items() if 'team' not in k} for r in records], reference), [])
        html = render_team_statistics(result)
        self.assertIn('England', html)
        self.assertIn('100.00%', html)


if __name__ == '__main__':
    unittest.main()
