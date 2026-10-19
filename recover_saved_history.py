"""Recover missing finalized perspectives from saved Eadriatic HTML, offline.

Existing perspectives are never overwritten. Conflicting snapshots are excluded.
Run without --apply to inspect the recovery summary.
"""
import argparse
from collections import defaultdict
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

from eadriatic_leagues import parse_history_records
from match_history import load_records, write_records_atomic

BASE = Path(__file__).resolve().parent
FIELDS = ('match_id', 'player_key', 'rival_key', 'timestamp_utc',
          'home_score', 'away_score', 'result', 'home_away')


def recover(existing, snapshots):
    """Return unchanged existing rows plus consistent new perspectives."""
    known = {r['perspective_id']: r for r in existing}
    candidates = defaultdict(list)
    for rows in snapshots:
        for row in rows:
            if row.get('result') in {'V', 'E', 'D'}:
                candidates[row['perspective_id']].append(row)
    added, conflicts = [], set()
    for identity, rows in candidates.items():
        comparisons = rows + ([known[identity]] if identity in known else [])
        if len({tuple(r.get(f) for f in FIELDS) for r in comparisons}) > 1:
            conflicts.update(r['match_id'] for r in rows)
        elif identity not in known:
            added.append(rows[0])
    added = [r for r in added if r['match_id'] not in conflicts]
    return existing + added, {'existing_perspectives': len(existing),
                              'added_perspectives': len(added),
                              'conflicting_matches_skipped': len(conflicts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    folder = BASE / 'eadriatic' / 'data'
    paths = sorted(folder.glob('*downloaded.html'))
    snapshots = []
    for path in paths:
        with redirect_stdout(StringIO()):
            snapshots.append(parse_history_records(path.read_text(encoding='utf-8'),
                                                   source_file=path.name))
    history_path = folder / 'match_history.jsonl'
    merged, summary = recover(load_records(history_path), snapshots)
    summary.update(saved_snapshots=len(paths), applied=args.apply)
    if args.apply and summary['added_perspectives']:
        write_records_atomic(history_path, merged)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
