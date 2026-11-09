"""Use dated, ordered rival sequences without inventing match timestamps."""
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from group_analysis import parse_vs_rivals
from match_history import name_key
from current_streaks_v2 import split_player_sessions, _record_time
from six_match_stats import horizon_observed, failure_series_metrics, pair_repeat_statistics, first_win_followups


def load_daily_pair_sequences(base, reference):
    lookup = defaultdict(dict)
    today = reference.astimezone(ZoneInfo('Europe/Madrid')).date()
    for league, folder in [('GT', 'gt'), ('EADRIATIC', 'eadriatic')]:
        for path in sorted((Path(base) / folder / 'data').glob('*_player_stats.txt')):
            try:
                day = datetime.strptime(path.name[:8], '%Y%m%d').date()
            except ValueError:
                continue
            if day >= today:
                continue  # A daily export still being updated is not a closed series.
            for player, rivals in parse_vs_rivals(path).items():
                for rival, stats in rivals.items():
                    seq = ''.join(stats['seq'])
                    # More than six can combine multiple sessions with no known boundary.
                    if 1 <= len(seq) <= 6 and len(seq) == stats['W'] + stats['D'] + stats['L']:
                        lookup[(league, name_key(player), name_key(rival))][day.isoformat()] = seq
                    elif not seq and stats['W'] + stats['D'] + stats['L'] == 6:
                        lookup[(league, name_key(player), name_key(rival))][day.isoformat()] = stats
    return lookup


def enrich_pair_stats(stats, player_records, reference, pair, daily):
    """Prefer one consistent daily sequence over partial detailed sessions on that date."""
    if not daily:
        return stats
    unique = {}
    for row in player_records:
        stamp = _record_time(row)
        if stamp is not None and stamp <= reference and row.get('result') in {'V', 'E', 'D'}:
            unique.setdefault((stamp, row.get('rival_key')), row)
    player_records = list(unique.values())
    observations = []
    day_results = defaultdict(list)
    seen = set()
    for row in sorted(player_records, key=lambda r: _record_time(r) or reference):
        stamp = _record_time(row)
        if (row.get('rival_key') != pair[2] or row.get('result') not in {'V', 'E', 'D'}
                or stamp is None or stamp > reference):
            continue
        key = (stamp, row.get('rival_key'))
        if key in seen:
            continue
        seen.add(key)
        day_results[stamp.astimezone(ZoneInfo('Europe/Madrid')).date().isoformat()].append(row['result'])
    for session in split_player_sessions(player_records):
        if _record_time(session[-1]) + timedelta(minutes=90) >= reference:
            continue
        rows = [r for r in session if r.get('rival_key') == pair[2] and r.get('result') in {'V', 'E', 'D'}]
        if rows:
            dates = {_record_time(r).astimezone(ZoneInfo('Europe/Madrid')).date().isoformat() for r in rows}
            observations.append((dates, ''.join(r['result'] for r in rows)))
    used = 0
    aggregate_complete = []
    for day, sequence in daily.items():
        affected = [(dates, seq) for dates, seq in observations if day in dates]
        if len(affected) > 1 or any(len(dates) != 1 for dates, _ in affected):
            continue  # Preserve sessions crossing midnight; do not count them twice.
        detailed = ''.join(day_results[day])
        if isinstance(sequence, dict):
            # W/D/L totals settle V≤6 for a six-match day, but cannot locate
            # its first win or condition on an unobserved initial prefix.
            if any(detailed.count(result) > sequence[field]
                   for result, field in [('V', 'W'), ('E', 'D'), ('D', 'L')]):
                continue
            if any(len(seq) >= 6 for _, seq in affected):
                continue
            known_six = any(horizon_observed(seq, 0, 6) for _, seq in affected)
            aggregate_complete.append((day, sequence['W'] > 0, known_six))
            used += 1
            continue
        iterator = iter(sequence)
        if not all(result in iterator for result in detailed):
            continue  # Conflicting exports cannot safely fill the gap.
        observations = [(dates, seq) for dates, seq in observations if day not in dates]
        observations.append(({day}, sequence))
        used += 1
    horizons = []
    for horizon in (4, 5, 6):
        for k in range(horizon):
            sequences = [seq for _, seq in observations
                         if 'V' not in seq[:k] and horizon_observed(seq, k, horizon)]
            wins = sum('V' in seq[k:horizon] for seq in sequences)
            sample = len(sequences)
            if horizon == 6 and k == 0:
                extras = [win for _, win, already_counted in aggregate_complete if not already_counted]
                sample += len(extras)
                wins += sum(extras)
            horizons.append(dict(league=pair[0], initial_without_win=k, horizon=horizon,
                                 sample=sample, win_pct=wins * 100 / sample if sample else None))
    complete = [seq for _, seq in observations if len(seq) == 6]
    events = [(max(dates), 'V' not in seq) for dates, seq in observations if len(seq) == 6]
    events.extend((day, not win) for day, win, _ in aggregate_complete)
    # Stable sorting retains known order for multiple detailed sessions on one day.
    events.sort(key=lambda item: item[0])
    intervals = failure_series_metrics(failed for _, failed in events)
    return {**stats, 'pair_horizons': horizons, 'complete_series': len(complete) + len(aggregate_complete),
            'pair_repeat_rows': pair_repeat_statistics((pair[0], seq) for _, seq in observations),
            'first_win_followups': first_win_followups((pair[0], seq) for _, seq in observations),
            **intervals,
            'zero_win_series': sum('V' not in seq for seq in complete) + sum(not win for _, win, _ in aggregate_complete),
            'daily_sequences_used': used}
