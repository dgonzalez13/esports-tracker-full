from copy import deepcopy
from email.message import EmailMessage
from html import escape
from pathlib import Path
from tests.test_match_history import workspace_tempdir
import unittest

from eadriatic_saved_results import (
    import_saved_results, parse_saved_results, read_saved_html,
)
from match_history import MatchHistoryError, merge_records, perspective_id


URL = 'https://es.betsapi.com/soccer/le/33440/esoccer-adriatic-league--10-mins-play/p.7'
HTML = f'''<!doctype html><html><head><meta charset="utf-8">
<link rel="canonical" href="{URL}"></head><body><table><tbody>
<tr><td data-dt="2026-10-19T15:45:00Z">10/19 15:45</td><td>-</td><td>
<a href="/soccer/t/1/home">Real Sociedad (Cleo) Esports</a> v
<a href="/soccer/t/2/away">Sevilla (Eric)</a></td>
<td><a href="/soccer/r/13309679/result">3-2</a></td></tr>
<tr><td data-dt="2026-10-19T15:50:00Z">10/19 15:50</td><td>-</td><td>
<a href="/soccer/t/1/home">Real Sociedad (Cleo) Esports</a> v
<a href="/soccer/t/2/away">Sevilla (Eric)</a></td><td>Cancelado</td></tr>
</tbody></table></body></html>'''


def official_copy(records, event='eadriatic:44449481'):
    rows = deepcopy(records)
    for row in rows:
        row.update(match_id=event, perspective_id=perspective_id(event, row['player']),
                   native_match_id=event.split(':')[-1], source_type='eadriatic_html',
                   source_file='official.html')
        row['timestamp_utc'] = row['timestamp_utc'].replace(':00Z', 'Z')
    return rows


class SavedResultsTests(unittest.TestCase):
    def parse(self, html=HTML):
        return parse_saved_results(html, 'example.html')

    def test_scores_players_and_utc_to_madrid(self):
        rows = self.parse()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['player']: r['result'] for r in rows}, {'Cleo': 'V', 'Eric': 'D'})
        self.assertEqual(rows[0]['timestamp'], '2026-10-19T17:45:00+02:00')
        self.assertEqual(rows[0]['match_id'], 'eadriatic:betsapi:13309679')
        self.assertFalse(rows[0]['timezone_inferred'])
        self.assertNotIn('round', rows[0])

    def test_wrong_league_timezone_and_missing_players_fail(self):
        for html in [HTML.replace('33440', '123'), HTML.replace('15:45:00Z', '15:45:00'),
                     HTML.replace('Real Sociedad (Cleo) Esports', 'Real Sociedad'),
                     '<html><title>Just a moment</title></html>']:
            with self.assertRaises(ValueError):
                self.parse(html)

    def test_midnight_dst_and_scoreless_draw(self):
        rows = self.parse(HTML.replace('15:45:00Z', '23:45:00Z').replace('3-2', '0-0'))
        self.assertEqual(rows[0]['timestamp'], '2026-10-20T01:45:00+02:00')
        self.assertEqual({r['result'] for r in rows}, {'E'})
        winter = self.parse(HTML.replace('2026-10-19', '2026-10-26'))
        self.assertEqual(winter[0]['timestamp'], '2026-10-26T16:45:00+01:00')

    def test_duplicate_html_rows_do_not_add_matches(self):
        self.assertEqual(len(self.parse(HTML.replace('</tbody>', HTML.split('<tbody>')[1].split('</tbody>')[0] + '</tbody>'))), 2)

    def test_mhtml_and_view_source_decode_utf8(self):
        source = '<table>' + ''.join('<tr><td class="line-content">' + escape(line) + '</td></tr>'
                                     for line in HTML.splitlines()) + '</table>'
        message = EmailMessage()
        message['Snapshot-Content-Location'] = URL
        part = EmailMessage()
        part.set_content(source, subtype='html', charset='utf-8', cte='quoted-printable')
        part['Content-Location'] = URL
        message.make_related()
        message.attach(part)
        with workspace_tempdir() as folder:
            path = Path(folder) / 'saved.mhtml'
            path.write_bytes(message.as_bytes())
            decoded, url = read_saved_html(path)
            self.assertEqual(url, URL)
            self.assertEqual(self.parse(decoded), self.parse())

    def test_cross_source_duplicate_in_both_import_orders(self):
        saved = self.parse()
        official = official_copy(saved)
        for existing, candidate in [(saved, official), (official, saved)]:
            original = deepcopy(existing)
            merged = merge_records(existing, candidate)
            self.assertEqual(len(merged), 2)
            self.assertEqual({r['match_id'] for r in merged}, {official[0]['match_id']})
            self.assertTrue(all(len(r['alternate_sources']) == 1 for r in merged))
            self.assertEqual(existing, original)  # No caller data is mutated.
            self.assertEqual(len(merge_records(merged, candidate)), 2)

    def test_score_conflicts_and_nearby_kickoffs_abort(self):
        saved = self.parse()
        changed = self.parse(HTML.replace('3-2', '4-2'))
        merged = merge_records(official_copy(saved), changed)
        self.assertTrue(all(r['home_score'] == 3 for r in merged))
        with self.assertRaises(MatchHistoryError):
            merge_records(official_copy(saved), self.parse(HTML.replace('15:45:00Z', '15:46:00Z')))
        with self.assertRaises(MatchHistoryError):
            merge_records(saved, self.parse(HTML.replace('3-2', '4-2')))

    def test_ambiguous_official_matches_abort(self):
        saved = self.parse()
        with self.assertRaises(MatchHistoryError):
            merge_records(official_copy(saved) + official_copy(saved, 'eadriatic:44449482'), saved)

    def test_preview_and_apply_are_idempotent_and_write_actual_date(self):
        with workspace_tempdir() as folder:
            root = Path(folder)
            source, history = root / 'saved.html', root / 'match_history.jsonl'
            source.write_text(HTML, encoding='utf-8')
            report = import_saved_results([source], history)
            self.assertFalse(history.exists())
            self.assertEqual(report['added_matches'], 1)
            import_saved_results([source], history, apply=True, complete_days=['2026-10-19'])
            self.assertEqual(len(history.read_text(encoding='utf-8').splitlines()), 2)
            daily = root / '20261019_eadriatic_player_stats.txt'
            self.assertIn('2026-10-19', daily.read_text(encoding='utf-8'))
            report = import_saved_results([source], history, apply=True)
            self.assertEqual(report['added_matches'], 0)
            self.assertEqual(len(history.read_text(encoding='utf-8').splitlines()), 2)
            self.assertTrue(list(root.glob('*.before_manual_*')))

    def test_partial_import_preserves_existing_daily_totals(self):
        with workspace_tempdir() as folder:
            root = Path(folder)
            source, history = root / 'saved.html', root / 'match_history.jsonl'
            source.write_text(HTML, encoding='utf-8')
            daily = root / '20261019_eadriatic_player_stats.txt'
            daily.write_text('existing daily totals', encoding='utf-8')
            report = import_saved_results([source], history, apply=True)
            self.assertEqual(daily.read_text(encoding='utf-8'), 'existing daily totals')
            self.assertEqual(report['daily_stats_pending_complete_export'], ['2026-10-19'])

    def test_manual_then_official_repair_corrects_and_does_not_duplicate(self):
        from datetime import datetime
        from match_history import load_records
        from repair_eadriatic_day import update_repaired_history

        official_html = '''<span class="fg-heading">FC26 R1(INTERNATIONAL)19.10.2026</span>
        <span class="time-heading">17:45</span>
        <table><tr data-match-href="/match/44449481.html">
        <td>Real Sociedad (Cleo)</td><td>1 - 4</td><td>Sevilla (Eric)</td></tr></table>'''
        with workspace_tempdir() as folder:
            root = Path(folder)
            source, history = root / 'saved.html', root / 'match_history.jsonl'
            source.write_text(HTML, encoding='utf-8')
            import_saved_results([source], history, apply=True)
            summary = update_repaired_history(official_html, datetime(2026, 10, 19), history_path=history)
            rows = load_records(history)
            self.assertEqual(len(rows), 2)
            self.assertEqual(summary['promoted_manual_perspectives'], 2)
            self.assertEqual({r['match_id'] for r in rows}, {'eadriatic:44449481'})
            self.assertTrue(all(r['source_type'] == 'eadriatic_html' for r in rows))
            self.assertTrue(all(r['home_score'] == 1 and r['away_score'] == 4 for r in rows))
            self.assertTrue(all(r.get('group_key') for r in rows))
            self.assertTrue(all(r['alternate_sources'][0]['home_score'] == 3 for r in rows))
            before = history.read_bytes()
            again = update_repaired_history(official_html, datetime(2026, 10, 19), history_path=history)
            self.assertEqual(again['updated_perspectives'], 0)
            self.assertEqual(history.read_bytes(), before)
            report = import_saved_results([source], history, apply=True)
            self.assertEqual(report['added_matches'], 0)
            self.assertTrue(all(r['home_score'] == 1 for r in load_records(history)))


if __name__ == '__main__':
    unittest.main()
