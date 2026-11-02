"""Current directional sequences and all pending published pair fixtures."""
from collections import defaultdict
from datetime import timedelta

from current_streaks_v2 import _record_time
from match_history import name_key


def cancelled_pair_counts(schedule, reference):
    """Cancelled slots among the first six published encounters in this window."""
    pairs = defaultdict(dict)
    for league, source in (schedule or {}).get('sources', {}).items():
        for row in source.get('records', []):
            stamp = _record_time(row)
            if stamp is None or stamp < reference - timedelta(hours=8):
                continue
            a, b = row.get('player_key'), row.get('rival_key')
            if not a or not b:
                continue
            pairs[(league, tuple(sorted((a, b))))][stamp] = row.get('fixture_status')
    return {key: sum(status == 'cancelled' for _, status in sorted(slots.items())[:6])
            for key, slots in pairs.items()}


def pair_series_schedule(records, schedule, reference):
    start = reference - timedelta(hours=8)
    finalized, sequences, pending = set(), defaultdict(list), {}

    def identity(row, league):
        stamp = _record_time(row)
        player = row.get('player') or row.get('player_key')
        rival = row.get('rival') or row.get('rival_key')
        if (stamp is None or not isinstance(player, str) or not player.strip()
                or not isinstance(rival, str) or not rival.strip()):
            return None
        player, rival = name_key(player), name_key(rival)
        return (league, tuple(sorted((player, rival))), stamp), player, rival

    # Prefer persisted results. Calendar finals supplement the current sequence
    # when the calendar has a confirmed result not collected by the history yet.
    calendar = [(league, row) for league, source in (schedule or {}).get('sources', {}).items()
                for row in source.get('records', [])]
    cancelled = {identity(row, league)[0] for league, row in calendar
                 if row.get('fixture_status') == 'cancelled' and identity(row, league)}
    for league, row in [(r.get('league'), r) for r in records] + calendar:
        item = identity(row, league)
        if not item or row.get('result') not in {'V', 'E', 'D'}:
            continue
        key, player, rival = item
        if key in cancelled:
            continue
        stamp = key[2]
        if stamp > reference or key in finalized:
            continue
        finalized.add(key)
        if stamp >= start:
            result = row['result']
            inverse = {'V': 'D', 'D': 'V', 'E': 'E'}[result]
            sequences[(league, player, rival)].append((stamp, result))
            sequences[(league, rival, player)].append((stamp, inverse))
    for league, row in calendar:
        item = identity(row, league)
        if (not item or row.get('result') or row.get('fixture_status') not in {'scheduled', 'unknown'}):
            continue
        key, _, _ = item
        if key in finalized or key[2] < start:
            continue
        pending[key] = {'timestamp': key[2].isoformat(), 'started': key[2] <= reference}
    fixtures = defaultdict(list)
    for (league, pair, stamp), row in sorted(pending.items()):
        fixtures[(league, pair)].append(row)
    return {key: ''.join(result for _, result in sorted(rows)) for key, rows in sequences.items()}, fixtures
