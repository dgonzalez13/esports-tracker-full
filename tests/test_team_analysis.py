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

    def test_ead_unique_matches_ignore_old_and_pending(self):
        records = parse_history_records(EAD_HTML, 'sample', include_scheduled=True)
        self.assertEqual(records[0]['player_team'], 'England')
        self.assertEqual(records[1]['player_team'], 'Belgium')
        reference = datetime(2026, 7, 15, tzinfo=timezone.utc)
        result = calculate_team_stats(records + records, reference)
        self.assertEqual(result['unique_matches'], 2)
        dexter = next(i for i, r in enumerate(result['players']) if r['name'] == 'Dexter')
        match = next(r for r in result['matches'] if dexter in (r[2], r[4]))
        self.assertEqual(match[6] if match[2] == dexter else {'V': 'D', 'D': 'V', 'E': 'E'}[match[6]], 'V')
        old = calculate_team_stats([{k:v for k,v in r.items() if 'team' not in k} for r in records], reference)
        self.assertEqual(old['unique_matches'], 0)
        html = render_team_statistics(result)
        self.assertIn('England', html)
        self.assertIn('team-stats-group', html)
        self.assertIn('team-stats-data', html)

    def test_deduplicates_physical_match_across_directions_and_source_ids(self):
        rows = parse_history_records(EAD_HTML, 'sample')[:2]
        alternate = [dict(r, match_id='eadriatic:betsapi:other') for r in rows]
        stats = calculate_team_stats(rows + alternate + list(reversed(rows)), datetime(2026, 7, 15, tzinfo=timezone.utc))
        self.assertEqual(stats['unique_matches'], 1)

    def test_source_team_ids_merge_aliases_and_missing_ids(self):
        fixture = gt_match()
        for participant, name, identity in zip(fixture['participants'], ['Madrid', 'Barcelona'], [17, 20]):
            participant['participant']['team'] = dict(name=name, id=identity)
        rows = build_history_records([fixture], 'sample')
        newer = [dict(r, match_id='gt:other', timestamp_utc='2026-10-22T23:30:00Z',
                      timestamp='2026-10-22T23:30:00Z',
                      player_team='Real Madrid' if r['player_team_id'] == 17 else r['player_team']) for r in rows]
        stats = calculate_team_stats(rows + newer, datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(len(stats['teams']), 2)
        self.assertEqual(stats['unique_matches'], 2)
        self.assertEqual(stats['last_date'], '2026-10-23')

    def test_page_payload_escapes_script_closing_tags(self):
        import json
        import re
        stats = {'schema_version': 1, 'players': [], 'teams': [{'name': '</script><b>unsafe</b>', 'league': 'GT'}],
                 'matches': [], 'unique_matches': 0}
        page = render_team_statistics(stats)
        self.assertNotIn('</script><b>unsafe</b>', page)
        payload = re.search(r'id="team-stats-data">(.*?)</script>', page).group(1)
        self.assertEqual(json.loads(payload)['teams'][0]['name'], '</script><b>unsafe</b>')

    def test_only_team_explorer_remains_among_general_statistics(self):
        from web_tracker.generate_site import render_page
        page = render_page({}, {})
        self.assertIn('id="team-statistics"', page)
        for identity in ('h2h-win-gap-statistics', 'repeat-win-statistics', 'six-match-statistics'):
            self.assertNotIn(identity, page)
        for identity in ('recent-group-h2h', 'active-repeat-matches', 'underdog-matchups'):
            self.assertIn('id="' + identity + '"', page)

    def test_known_team_abbreviations_are_grouped_without_guessing_other_clubs(self):
        from team_analysis import canonical_team_name
        self.assertEqual(canonical_team_name('Bayern M.'), canonical_team_name('Bayern Munich'))
        self.assertEqual(canonical_team_name('A.Madrid'), canonical_team_name('Atletico Madrid'))
        self.assertEqual(canonical_team_name('PSG'), canonical_team_name('Paris Saint-Germain'))
        self.assertNotEqual(canonical_team_name('Bayer 04'), canonical_team_name('Bayern Munich'))
        rows = parse_history_records(EAD_HTML, 'sample')[:1]
        rows[0].update(player_team='Bayern M.', rival_team='PSG')
        newer = dict(rows[0], match_id='eadriatic:newer', timestamp_utc='2026-07-14T10:00:00Z',
                     player_team='Bayern Munich', rival_team='Paris Saint-Germain')
        dataset = calculate_team_stats(rows + [newer], datetime(2026, 7, 15, tzinfo=timezone.utc))
        self.assertEqual(dataset['unique_matches'], 2)
        self.assertEqual(len(dataset['teams']), 2)


if __name__ == '__main__':
    unittest.main()
