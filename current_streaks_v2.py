"""Session-aware current streaks calculated from normalized match history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, TypedDict
from zoneinfo import ZoneInfo

from history_query import EADRIATIC_HISTORY_PATH, GT_HISTORY_PATH, load_all_history
from match_history import name_key
from selected_players import TrackedPlayer, load_tracked_players


DEFAULT_SESSION_GAP_MINUTES = 90
DEFAULT_ACTIVE_WINDOW_MINUTES = 180
DEFAULT_OPERATIONAL_WINDOW_HOURS = 8
MADRID = ZoneInfo("Europe/Madrid")


class PlayerSession(TypedDict):
    session_id: str
    league: str
    player: str
    player_key: str
    session_number: int
    start_timestamp: str
    end_timestamp: str
    start_local: str
    end_local: str
    duration_minutes: int
    played: int
    wins: int
    draws: int
    losses: int
    win_pct: float
    draw_pct: float
    loss_pct: float
    sequence: str
    last_10: str
    current_streak_result: str | None
    current_streak: int
    tracked: bool
    balance: str
    active: bool


class CurrentStreaksV2Payload(TypedDict):
    generated_at: str
    session_gap_minutes: int
    active_window_minutes: int
    leagues: dict[str, list[PlayerSession]]


__all__ = [
    "DEFAULT_SESSION_GAP_MINUTES", "DEFAULT_ACTIVE_WINDOW_MINUTES",
    "DEFAULT_OPERATIONAL_WINDOW_HOURS", "calculate_operational_snapshot",
    "build_current_streaks_v2_payload",
    "PlayerSession", "CurrentStreaksV2Payload", "player_session_history",
    "split_player_sessions", "calculate_player_session",
    "calculate_current_streaks_v2", "load_current_streaks_v2",
]


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("reference_time must be a datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _record_time(record: dict[str, Any]) -> datetime | None:
    raw = record.get("timestamp_utc") or record.get("timestamp")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sort_key(record: dict[str, Any]) -> tuple[datetime, str, str]:
    return (
        _record_time(record) or datetime.min.replace(tzinfo=timezone.utc),
        str(record.get("match_id", "")), str(record.get("perspective_id", "")),
    )


def _positive_minutes(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be an integer greater than zero")
    return value


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def player_session_history(records, league: str, player: str) -> list[dict[str, Any]]:
    if not isinstance(league, str) or not league.strip():
        raise ValueError("league must be a non-empty string")
    if not isinstance(player, str) or not player.strip():
        raise ValueError("player must be a non-empty string")
    league_key = league.strip().casefold()
    player_key = name_key(player)
    rows = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record_league = record.get("league")
        if not isinstance(record_league, str) or record_league.strip().casefold() != league_key:
            continue
        if record.get("player_key") != player_key or record.get("result") not in {"V", "E", "D"}:
            continue
        if _record_time(record) is None:
            continue
        rows.append(dict(record))
    return sorted(rows, key=_sort_key)


def split_player_sessions(records, *, session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES):
    gap = _positive_minutes(session_gap_minutes, "session_gap_minutes")
    ordered = sorted(
        (dict(record) for record in records if isinstance(record, dict) and _record_time(record) is not None),
        key=_sort_key,
    )
    if not ordered:
        return []
    sessions = [[ordered[0]]]
    for record in ordered[1:]:
        previous = sessions[-1][-1]
        if (_record_time(record) - _record_time(previous)).total_seconds() > gap * 60:
            sessions.append([])
        sessions[-1].append(record)
    return sessions


def calculate_player_session(
    records, *, league, player, player_key, session_number, tracked,
    reference_time, active_window_minutes=DEFAULT_ACTIVE_WINDOW_MINUTES,
):
    active_window = _positive_minutes(active_window_minutes, "active_window_minutes")
    reference = _utc(reference_time)
    ordered = sorted(
        (dict(record) for record in records if isinstance(record, dict) and record.get("result") in {"V", "E", "D"} and _record_time(record) is not None),
        key=_sort_key,
    )
    if not ordered:
        raise ValueError("records must contain at least one valid match")
    start, end = _record_time(ordered[0]), _record_time(ordered[-1])
    sequence = "".join(record["result"] for record in ordered)
    wins, draws, losses = sequence.count("V"), sequence.count("E"), sequence.count("D")
    played = len(sequence)
    streak_result = sequence[-1] if sequence else None
    streak = 0
    for result in reversed(sequence):
        if result != streak_result:
            break
        streak += 1
    balance = ""
    if tracked and wins >= draws + losses:
        balance = "🟢"
    elif tracked and losses >= wins + draws:
        balance = "🔴"
    elapsed = (reference - end).total_seconds()
    active = 0 <= elapsed <= active_window * 60
    league_name = str(league).strip().upper()
    start_token = start.strftime("%Y%m%dT%H%M%SZ")
    return {
        "session_id": f"{league_name.casefold()}:{player_key}:{start_token}",
        "league": league_name, "player": str(player).strip(), "player_key": player_key,
        "session_number": session_number, "start_timestamp": _z(start), "end_timestamp": _z(end),
        "start_local": start.astimezone(MADRID).isoformat(),
        "end_local": end.astimezone(MADRID).isoformat(),
        "duration_minutes": int((end - start).total_seconds() // 60),
        "played": played, "wins": wins, "draws": draws, "losses": losses,
        "win_pct": round(wins / played * 100, 2),
        "draw_pct": round(draws / played * 100, 2),
        "loss_pct": round(losses / played * 100, 2),
        "sequence": sequence, "last_10": sequence[-10:],
        "current_streak_result": streak_result, "current_streak": streak,
        "tracked": bool(tracked), "balance": balance, "active": active,
    }


def calculate_current_streaks_v2(
    records, tracked_players, *, reference_time,
    session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES,
    active_window_minutes=DEFAULT_ACTIVE_WINDOW_MINUTES,
    window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS,
):
    gap = _positive_minutes(session_gap_minutes, "session_gap_minutes")
    active_window = _positive_minutes(active_window_minutes, "active_window_minutes")
    reference = _utc(reference_time)
    materialized = list(records)
    snapshot = calculate_operational_snapshot(
        materialized, tracked_players, reference_time=reference,
        window_hours=window_hours,
    )
    payload = build_current_streaks_v2_payload(snapshot, reference_time=reference, window_hours=window_hours)
    # Deprecated payload keys remain for callers from TASK-007.
    payload["session_gap_minutes"] = gap
    payload["active_window_minutes"] = active_window
    # Preserve useful session numbering without allowing sessions to affect stats.
    for rows in payload["leagues"].values():
        for row in rows:
            history = player_session_history(materialized, row["league"], row["player"])
            row["session_number"] = len(split_player_sessions(history, session_gap_minutes=gap))
    return payload


def _positive_hours(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("window_hours must be an integer greater than zero")
    return value


def calculate_operational_snapshot(
    records, tracked_players, *, reference_time,
    window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS,
):
    """Return immutable per-player statistics for one bounded UTC window."""
    reference = _utc(reference_time)
    hours = _positive_hours(window_hours)
    lower = reference - timedelta(hours=hours)
    materialized = [dict(row) for row in records if isinstance(row, dict)]
    identities = {}
    for row in tracked_players:
        if not row.get("tracked") or not row.get("bettable", True):
            continue
        league, key, player = row.get("league"), row.get("player_key"), row.get("player")
        if not all(isinstance(value, str) and value.strip() for value in (league, key, player)):
            continue
        identities.setdefault((league.strip().upper(), key), row)
    snapshot = []
    for (league, key), row in identities.items():
        history = player_session_history(materialized, league, row["player"])
        history = [event for event in history if lower <= _record_time(event) <= reference]
        if not history:
            continue
        sequence = "".join(event["result"] for event in history)
        wins, draws, losses = sequence.count("V"), sequence.count("E"), sequence.count("D")
        played = len(sequence)
        streak_result = sequence[-1]
        streak = 0
        for result in reversed(sequence):
            if result != streak_result:
                break
            streak += 1
        indicator = "GREEN" if wins >= draws + losses else (
            "RED" if losses >= wins + draws else "NONE"
        )
        snapshot.append({
            "league": league, "player": row["player"], "player_key": key,
            "wins": wins, "draws": draws, "losses": losses, "played": played,
            "win_pct": round(wins / played * 100, 2),
            "draw_pct": round(draws / played * 100, 2),
            "loss_pct": round(losses / played * 100, 2),
            "sequence": sequence, "last_10": sequence[-10:],
            "current_streak_result": streak_result, "current_streak": streak,
            "balance": "🟢" if indicator == "GREEN" else ("🔴" if indicator == "RED" else ""),
            "indicator": indicator, "tracked": True,
        })
    snapshot.sort(key=lambda row: (
        row["league"], -row["wins"], -row["win_pct"], -row["played"],
        row["player"].casefold(), row["player_key"],
    ))
    return snapshot


def build_current_streaks_v2_payload(snapshot, *, reference_time, window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS):
    reference = _utc(reference_time)
    hours = _positive_hours(window_hours)
    leagues = {"GT": [], "EADRIATIC": []}
    for source in snapshot:
        row = dict(source)
        league = str(row.get("league", "")).upper()
        if not league:
            continue
        leagues.setdefault(league, []).append(row)
    for rows in leagues.values():
        rows.sort(key=lambda row: (-row["wins"], -row["win_pct"], -row["played"], row["player"].casefold()))
    return {
        "generated_at": _z(reference), "operational_window_hours": hours, "leagues": leagues,
    }


def load_current_streaks_v2(
    tracked_players_path: str | Path, gt_path=GT_HISTORY_PATH,
    eadriatic_path=EADRIATIC_HISTORY_PATH, *, reference_time=None,
    session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES,
    active_window_minutes=DEFAULT_ACTIVE_WINDOW_MINUTES,
    window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS,
):
    reference = _utc(reference_time or datetime.now(timezone.utc))
    tracked = load_tracked_players(tracked_players_path)
    records = load_all_history(gt_path, eadriatic_path)
    return calculate_current_streaks_v2(
        records, tracked, reference_time=reference,
        session_gap_minutes=session_gap_minutes,
        active_window_minutes=active_window_minutes,
        window_hours=window_hours,
    )
