from datetime import datetime, timedelta, timezone
import unittest

from tests.test_h2h_analysis import perspective
from six_match_stats import calculate_six_match_stats
from web_tracker.historical_pair_series import enrich_pair_stats
from web_tracker.historical_pair_series import load_daily_pair_sequences
from tests.test_match_history import workspace_tempdir
from pathlib import Path


class ArchiveSeriesTests(unittest.TestCase):
    reference = datetime(2026, 9, 4, tzinfo=timezone.utc)
    pair = ('GT', 'david', 'fox')

    def rows(self, seq):
        return [perspective(i, result, timestamp=(datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
                                                 + timedelta(minutes=i)).isoformat())
                for i, result in enumerate(seq)]

    def stats(self, seq, daily):
        rows = self.rows(seq)
        stats = calculate_six_match_stats(rows, self.reference, pair=self.pair)
        return enrich_pair_stats(stats, rows, self.reference, self.pair, daily)

    def samples(self, result, k=0):
        return [r['sample'] for r in result['pair_horizons'] if r['initial_without_win'] == k]

    def test_ordered_archive_fills_partial_without_duplicate(self):
        result = self.stats('DD', {'2026-09-01': 'DDDDDV', '2026-09-02': 'VDDDDD'})
        self.assertEqual(result['complete_series'], 2)
        self.assertEqual(self.samples(result), [2, 2, 2])
        self.assertEqual(self.samples(result, 2), [1, 1, 1])
        full = self.stats('DDDDDV', {'2026-09-01': 'DDDDDV'})
        self.assertEqual(self.samples(full), [1, 1, 1])

    def test_aggregate_can_only_add_unconditional_six_horizon(self):
        totals = {'W': 1, 'D': 0, 'L': 5, 'seq': []}
        result = self.stats('', {'2026-09-01': totals})
        self.assertEqual(self.samples(result), [0, 0, 1])
        self.assertEqual(self.samples(result, 1), [0, 0, 0])
        self.assertEqual(result['complete_series'], 1)
        self.assertEqual(result['zero_win_series'], 0)

    def test_aggregate_does_not_duplicate_partial_resolved_win(self):
        totals = {'W': 1, 'D': 0, 'L': 5, 'seq': []}
        result = self.stats('VD', {'2026-09-01': totals})
        self.assertEqual(self.samples(result), [1, 1, 1])
        self.assertEqual(result['complete_series'], 1)

    def test_complete_aggregate_does_not_duplicate_full_jsonl(self):
        result = self.stats('VDDDDD', {'2026-09-01': {'W': 1, 'D': 0, 'L': 5}})
        self.assertEqual(result['complete_series'], 1)
        self.assertEqual(self.samples(result), [1, 1, 1])

    def test_conflicting_archive_does_not_replace_details(self):
        result = self.stats('VV', {'2026-09-01': 'DDDDDD'})
        self.assertEqual(result['complete_series'], 0)
        self.assertEqual(self.samples(result), [1, 1, 1])
        result = self.stats('VV', {'2026-09-01': {'W': 1, 'D': 0, 'L': 5}})
        self.assertEqual(result['complete_series'], 0)

    def test_six_no_win_failure_from_aggregate(self):
        result = self.stats('', {'2026-09-01': {'W': 0, 'D': 2, 'L': 4}})
        self.assertEqual(result['zero_win_series'], 1)
        row = next(r for r in result['pair_horizons'] if r['horizon'] == 6 and r['initial_without_win'] == 0)
        self.assertEqual(row['win_pct'], 0)

    def test_duplicate_sources_do_not_duplicate_archive_counts(self):
        rows = self.rows('DDDDDV')
        result = enrich_pair_stats({}, rows + rows, self.reference, self.pair,
                                   {'2026-09-01': 'DDDDDV'})
        self.assertEqual(result['complete_series'], 1)
        self.assertEqual(self.samples(result), [1, 1, 1])

    def test_loader_uses_only_closed_dates_and_six_aggregate_counts(self):
        with workspace_tempdir() as tmp:
            folder = Path(tmp) / 'gt' / 'data'
            folder.mkdir(parents=True)
            content = ('VS RIVALES\nDavid\nFox: 6 (50.0%/0.0%/50.0%)\n'
                       'Other: 5 (60.0%/0.0%/40.0%)\n')
            (folder / '20260901_player_stats.txt').write_text(content, encoding='utf-8')
            (folder / '20260904_player_stats.txt').write_text(content, encoding='utf-8')
            result = load_daily_pair_sequences(tmp, self.reference)
            self.assertEqual(list(result[self.pair]), ['2026-09-01'])
            self.assertEqual(result[self.pair]['2026-09-01']['W'], 3)
            self.assertNotIn(('GT', 'david', 'other'), result)
