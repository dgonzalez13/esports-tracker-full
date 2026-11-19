"""Possible pending encounters inferred from recent saved results, never fixtures."""
from datetime import timedelta

from current_streaks_v2 import _record_time
from eadriatic_saved_results import SOURCE_TYPE
from web_tracker.pair_series_schedule import pair_series_schedule


def infer_eadriatic_pairs(records, reference, published_fixtures):
    recent = [row for row in records if row.get('league') == 'EADRIATIC'
              and row.get('result') in {'V', 'E', 'D'}
              and _record_time(row) is not None
              and reference - timedelta(hours=8) <= _record_time(row) <= reference]
    sequences, _ = pair_series_schedule(recent, {}, reference)
    manual_pairs, names, latest = set(), {}, {}
    for row in recent:
        a, b = row.get('player_key'), row.get('rival_key')
        if not a or not b or a == b:
            continue
        pair = tuple(sorted((a, b)))
        names[a], names[b] = row.get('player', a), row.get('rival', b)
        stamp = _record_time(row)
        latest[pair] = max(stamp, latest.get(pair, stamp))
        if row.get('source_type') == SOURCE_TYPE:
            manual_pairs.add(pair)
    result = []
    for a, b in sorted(manual_pairs):
        sequence = sequences.get(('EADRIATIC', a, b), '')
        played = len(sequence)
        if (not 0 < played < 6
                or published_fixtures.get(('EADRIATIC', (a, b)))):
            continue
        result.append(dict(player=names[a], rival=names[b], player_key=a, rival_key=b,
                           observed=played, possible_remaining=6-played,
                           last_result=latest[(a, b)].isoformat()))
    return sorted(result, key=lambda row: row['last_result'], reverse=True)
