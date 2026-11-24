"""Directional pair sequences for the current calendar day in Madrid."""
from zoneinfo import ZoneInfo

from current_streaks_v2 import _record_time
from match_history import name_key


def daily_pair_sequences(records, schedule, reference):
    midnight = reference.astimezone(ZoneInfo('Europe/Madrid')).replace(hour=0, minute=0, second=0, microsecond=0)
    calendar = [dict(row, league=league)
                for league, source in (schedule or {}).get('sources', {}).items()
                for row in source.get('records', [])]
    def identity(row):
        stamp = _record_time(row)
        player, rival = row.get('player') or row.get('player_key'), row.get('rival') or row.get('rival_key')
        if not all(isinstance(name, str) and name.strip() for name in (player, rival)):
            return None
        a, b = name_key(player), name_key(rival)
        if stamp is None or not a or not b or a == b or not row.get('league'):
            return None
        return row['league'], tuple(sorted((a, b))), stamp
    cancelled = {identity(row) for row in calendar if row.get('fixture_status') == 'cancelled'}
    seen, pairs = set(), {}
    for row in list(records) + calendar:
        key = identity(row)
        if key is None or key in cancelled or key in seen or row.get('result') not in {'V', 'E', 'D'}:
            continue
        league, pair, stamp = key
        if not midnight <= stamp <= reference:
            continue
        seen.add(key)
        a = name_key(row.get('player') or row.get('player_key'))
        result = row['result']
        inverse = {'V': 'D', 'D': 'V', 'E': 'E'}[result]
        a_result = result if a == pair[0] else inverse
        pairs.setdefault((league, pair[0], pair[1]), []).append((stamp, a_result))
        pairs.setdefault((league, pair[1], pair[0]), []).append((stamp, {'V': 'D', 'D': 'V', 'E': 'E'}[a_result]))
    return {key: ''.join(result for _, result in sorted(rows)) for key, rows in pairs.items()}
