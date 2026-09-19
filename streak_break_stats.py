"""Conditional SG/SP outcomes for independent, already delimited windows."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
STARTS = {"GT": (5, 13, 21), "EADRIATIC": (7, 15, 23)}
OFFSETS = {"GT": 60, "EADRIATIC": 20}


def historical_windows(records, reference_time):
    """Infer rosters in the shared core of two staggered scheduled windows.

    Connected opponents identify a roster, not today's tracked-player order.
    Require an observed match at its scheduled start; reject ambiguous rosters.
    Midnight never splits a window. DST uses local scheduled boundaries, capped
    at eight elapsed hours. Duplicate perspectives never add matches.
    """
    by_league = defaultdict(list)
    seen = set()
    for row in records:
        league = row.get("league", "").upper()
        if league not in STARTS or row.get("result") not in {"V", "E", "D"}:
            continue
        try:
            stamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue
        if stamp.tzinfo is None or stamp > reference_time:
            continue
        identity = (league, row.get("match_id"), row.get("player_key"))
        if not all(identity) or not row.get("rival_key") or identity in seen:
            continue
        seen.add(identity)
        by_league[league].append((stamp.astimezone(timezone.utc), row))
    windows = []
    for league, events in by_league.items():
        events.sort(key=lambda item: (item[0], item[1]["match_id"]))
        first = events[0][0].astimezone(MADRID).date() - timedelta(days=1)
        last = events[-1][0].astimezone(MADRID).date()
        day = first
        while day <= last:
            for hour in STARTS[league]:
                base = datetime(day.year, day.month, day.day, hour, tzinfo=MADRID)
                second = base + timedelta(minutes=OFFSETS[league])
                next_base = base + timedelta(hours=8)
                bounds = [value.astimezone(timezone.utc) for value in (base, second, next_base)]
                core = [(t, r) for t, r in events if bounds[1] <= t < bounds[2]]
                graph = defaultdict(set)
                for _, row in core:
                    a, b = row["player_key"], row["rival_key"]
                    graph[a].add(b)
                    graph[b].add(a)
                visited = set()
                for player in sorted(graph):
                    if player in visited:
                        continue
                    roster, pending = set(), [player]
                    while pending:
                        key = pending.pop()
                        if key in roster:
                            continue
                        roster.add(key)
                        pending.extend(graph[key] - roster)
                    visited.update(roster)
                    if not 4 <= len(roster) <= 5:
                        continue
                    extended_end = (next_base + timedelta(minutes=OFFSETS[league])).astimezone(timezone.utc)
                    candidates = [(t, r) for t, r in events
                                  if bounds[0] <= t < extended_end
                                  and r["player_key"] in roster and r["rival_key"] in roster]
                    if not candidates:
                        continue
                    earliest = candidates[0][0]
                    if earliest not in bounds[:2]:
                        continue
                    stream = 1 if earliest == bounds[0] else 2
                    end = min(earliest + timedelta(hours=8),
                              bounds[2] if stream == 1 else extended_end)
                    by_player = defaultdict(list)
                    for stamp, row in candidates:
                        if earliest <= stamp < end:
                            by_player[row["player_key"]].append((stamp, row))
                    for key, matches in by_player.items():
                        windows.append({
                            "league": league, "player_key": key,
                            "player": matches[-1][1]["player"], "stream": stream,
                            "start": earliest.isoformat(), "end": end.isoformat(),
                            "sequence": "".join(row["result"] for _, row in matches),
                            "last_timestamp": matches[-1][0].isoformat(),
                        })
            day += timedelta(days=1)
    return windows


def pending_matches(schedule, league, key, active, reference_time, finished_ids):
    """Count only published future fixtures in this player's current turn.

    None means no usable calendar coverage, not zero remaining matches.
    """
    source = (schedule or {}).get("sources", {}).get(league, {})
    if not active or not source.get("updated_at") or source.get("error"):
        return None
    start, end = (datetime.fromisoformat(active[field]) for field in ("start", "end"))
    seen, covered = set(), False
    for row in source.get("records", []):
        if row.get("player_key") != key:
            continue
        try:
            stamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if stamp.tzinfo is None or not start <= stamp < end:
            continue
        covered = True
        if (stamp < reference_time or row.get("result") in {"V", "E", "D"}
                or row.get("fixture_status") != "scheduled"
                or (league, row.get("match_id")) in finished_ids):
            continue
        seen.add(row.get("match_id") or (stamp.isoformat(), row.get("rival_key")))
    return len(seen) if covered else None


def build_streak_statistics(records, reference_time, excluded_keys=(), *, tracked_players=(), schedule=None):
    records = list(records)
    tracked = {(row["league"], row["player_key"]) for row in tracked_players
               if row.get("tracked") and row.get("bettable", True)}
    finished_ids = {(row.get("league"), row.get("match_id")) for row in records
                    if row.get("result") in {"V", "E", "D"}}
    windows = historical_windows(records, reference_time)
    grouped = defaultdict(list)
    for window in windows:
        identity = (window["league"], window["player_key"])
        if identity not in excluded_keys:
            grouped[identity].append(window)
    leagues = {}
    for league in STARTS:
        players = []
        league_sequences = []
        for (row_league, key), entries in sorted(grouped.items()):
            if row_league != league:
                continue
            sequences = [entry["sequence"] for entry in entries]
            league_sequences.extend(sequences)
            active = next((entry for entry in reversed(entries)
                           if datetime.fromisoformat(entry["start"]) <= reference_time
                           < datetime.fromisoformat(entry["end"])), None)
            current = {}
            if active:
                for kind, breaker in (("SG", "V"), ("SP", "D")):
                    current[kind] = len(active["sequence"].split(breaker)[-1])
            if (league, key) not in tracked:
                continue
            players.append({"player": entries[-1]["player"], "player_key": key,
                            "league": league,
                            "remaining": pending_matches(schedule, league, key, active,
                                                         reference_time, finished_ids),
                            "current_end": active["end"] if active else None,
                            "current": current, "windows": len(entries),
                            "rows": summarize_windows(sequences)})
        selected = [w for w in windows if w["league"] == league
                    and (league, w["player_key"]) not in excluded_keys]
        leagues[league] = {
            "players": players, "rows": summarize_windows(league_sequences),
            "windows": len(selected),
            "from": min((w["start"] for w in selected), default=None),
            "to": max((w["last_timestamp"] for w in selected), default=None),
        }
    return {"leagues": leagues, "generated_at": reference_time.isoformat()}


def window_observations(sequence):
    """Yield each attained run length once per run, never beyond this window.

    A horizon is resolved by a break or by observing all its matches. Otherwise
    it is incomplete. Window boundaries must be supplied by the caller.
    """
    if any(result not in "VED" for result in sequence):
        raise ValueError("sequence must contain only V, E or D")
    for kind, breaker in (("SG", "V"), ("SP", "D")):
        length = 0
        for index, result in enumerate(sequence):
            length = 0 if result == breaker else length + 1
            if not length:
                continue
            outcomes = {}
            for horizon in (1, 2, 3):
                following = sequence[index + 1:index + 1 + horizon]
                outcomes[horizon] = (
                    "broken" if breaker in following else
                    "continued" if len(following) == horizon else "incomplete"
                )
            yield kind, length, outcomes


def summarize_windows(sequences):
    """Aggregate distinct windows; expose a separate denominator per horizon."""
    counts = defaultdict(lambda: {
        horizon: {"broken": 0, "continued": 0, "incomplete": 0}
        for horizon in (1, 2, 3)
    })
    for sequence in sequences:
        for kind, length, outcomes in window_observations(sequence):
            for horizon, outcome in outcomes.items():
                counts[kind, length][horizon][outcome] += 1
    rows = []
    for (kind, length), horizons in sorted(counts.items()):
        for values in horizons.values():
            resolved = values["broken"] + values["continued"]
            values["resolved"] = resolved
            values["break_pct"] = (
                round(100 * values["broken"] / resolved, 2) if resolved else None
            )
        rows.append({"kind": kind, "length": length, "horizons": horizons})
    return rows
