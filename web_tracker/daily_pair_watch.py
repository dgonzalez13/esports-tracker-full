"""Directional pair sequences for the current calendar day in Madrid."""
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta

from current_streaks_v2 import _record_time
from match_history import name_key


def daily_pair_events(records, schedule, reference):
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
    for row in calendar:
        key = identity(row)
        if (key is None or key in cancelled or key in seen or row.get('result')
                or row.get('fixture_status') not in {'scheduled', 'unknown', 'finished'}):
            continue
        league, pair, stamp = key
        if stamp < midnight:
            continue
        seen.add(key)
        pairs.setdefault((league, pair[0], pair[1]), []).append((stamp, None))
        pairs.setdefault((league, pair[1], pair[0]), []).append((stamp, None))
    return {key: [dict(timestamp=stamp.isoformat(), result=result) for stamp, result in sorted(rows)]
            for key, rows in pairs.items()}


def daily_pair_sequences(records, schedule, reference):
    return {key: ''.join(event['result'] for event in events if event['result'])
            for key, events in daily_pair_events(records, schedule, reference).items()
            if any(event['result'] for event in events)}


def watch_fixtures(rival):
    fixtures = rival.get('pair_fixtures', [])
    estimated = False
    if not fixtures and not rival.get('next_match'):
        fixtures = rival.get('inferred_pair', {}).get('estimated_fixtures', [])
        estimated = bool(fixtures)
    values = [fixture.get('timestamp') for fixture in fixtures] or [rival.get('next_match')]
    result = []
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            result.append(dict(timestamp=stamp.isoformat(), estimated=estimated))
        except ValueError:
            continue
    return result


def daily_watch_state(rival, reference):
    fixtures = watch_fixtures(rival)
    events = {event['timestamp']: event for event in rival.get('daily_pair_events', [])}
    for fixture in fixtures:
        events.setdefault(fixture['timestamp'], dict(timestamp=fixture['timestamp'], result=None))
    today = reference.astimezone(ZoneInfo('Europe/Madrid')).date()
    cutoff = reference - timedelta(minutes=15)
    sequence = ''
    for event in sorted(events.values(), key=lambda event: datetime.fromisoformat(event['timestamp'])):
        stamp = datetime.fromisoformat(event['timestamp'])
        if stamp.astimezone(ZoneInfo('Europe/Madrid')).date() != today or stamp > reference:
            continue
        sequence += event['result'] or ('?' if stamp <= cutoff else '')
    if 'daily_pair_events' not in rival and not any(event.get('result') for event in events.values()):
        sequence = rival.get('daily_pair_sequence', '') + sequence
    eligible = [f for f in fixtures if datetime.fromisoformat(f['timestamp']) > cutoff]
    next_fixture = min(eligible, key=lambda f: datetime.fromisoformat(f['timestamp'])) if eligible else None
    return sequence, next_fixture, dict(events=list(events.values()), fixtures=fixtures,
                                         fallback_sequence=rival.get('daily_pair_sequence', '') if 'daily_pair_events' not in rival else '')


def next_pair_time(rival):
    fixtures = rival.get('pair_fixtures', [])
    estimated = False
    if not fixtures and not rival.get('next_match'):
        fixtures = rival.get('inferred_pair', {}).get('estimated_fixtures', [])
        estimated = bool(fixtures)
    stamps = []
    values = [fixture.get('timestamp') for fixture in fixtures] or [rival.get('next_match')]
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            stamps.append(stamp)
        except ValueError:
            continue
    return (min(stamps), estimated) if stamps else (None, False)
