"""Read-only queries over normalized match-history JSONL records."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from match_history import name_key


BASE_DIR = Path(__file__).resolve().parent
GT_HISTORY_PATH = BASE_DIR / "gt" / "data" / "match_history.jsonl"
EADRIATIC_HISTORY_PATH = BASE_DIR / "eadriatic" / "data" / "match_history.jsonl"


class HistoryQueryError(Exception):
    """Base error raised while reading or querying match history."""


__all__ = [
    "HistoryQueryError",
    "BASE_DIR",
    "GT_HISTORY_PATH",
    "EADRIATIC_HISTORY_PATH",
    "load_history",
    "load_gt_history",
    "load_eadriatic_history",
    "load_all_history",
    "filter_by_league",
    "player_history",
    "player_vs_rival",
    "head_to_head",
    "filter_by_time",
    "latest_matches",
    "duplicate_perspective_ids",
]


def _sort_value(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    return "" if value is None else str(value)


def _sort_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(
        _sort_value(record, field)
        for field in (
            "timestamp_utc", "timestamp", "match_id", "player_key", "perspective_id"
        )
    )


def _copy_sorted(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return shallow record copies in deterministic chronological order."""
    return sorted((dict(record) for record in records), key=_sort_key)


def _normalized_league(league: str) -> str:
    if not isinstance(league, str) or not league.strip():
        raise ValueError("league must be a non-empty string")
    return league.strip().casefold()


def _normalized_name(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return name_key(value)


def load_history(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL history file; a missing file is an empty history."""
    history_path = Path(path)
    if not history_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with history_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HistoryQueryError(
                    f"invalid JSON in {history_path} at line {line_number}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                cause = TypeError(f"expected JSON object, got {type(value).__name__}")
                raise HistoryQueryError(
                    f"invalid record in {history_path} at line {line_number}: {cause}"
                ) from cause
            records.append(value)
    return _copy_sorted(records)


def load_gt_history(path: str | Path = GT_HISTORY_PATH) -> list[dict[str, Any]]:
    """Load the GT history from its project path or an override."""
    return load_history(path)


def load_eadriatic_history(
    path: str | Path = EADRIATIC_HISTORY_PATH,
) -> list[dict[str, Any]]:
    """Load the EADRIATIC history from its project path or an override."""
    return load_history(path)


def load_all_history(
    gt_path: str | Path = GT_HISTORY_PATH,
    eadriatic_path: str | Path = EADRIATIC_HISTORY_PATH,
) -> list[dict[str, Any]]:
    """Load, combine and chronologically sort both project histories."""
    return _copy_sorted([*load_history(gt_path), *load_history(eadriatic_path)])


def filter_by_league(
    records: Iterable[dict[str, Any]], league: str
) -> list[dict[str, Any]]:
    """Select records whose league matches case-insensitively."""
    target = _normalized_league(league)
    return _copy_sorted(
        record
        for record in records
        if isinstance(record.get("league"), str)
        and record["league"].strip().casefold() == target
    )


def player_history(
    records: Iterable[dict[str, Any]], player: str, league: str | None = None
) -> list[dict[str, Any]]:
    """Select perspectives belonging to one player, optionally in one league."""
    target = _normalized_name(player, "player")
    selected = (
        record for record in records if record.get("player_key") == target
    )
    return filter_by_league(selected, league) if league is not None else _copy_sorted(selected)


def player_vs_rival(
    records: Iterable[dict[str, Any]],
    player: str,
    rival: str,
    league: str | None = None,
) -> list[dict[str, Any]]:
    """Select only the player's perspectives against the requested rival."""
    player_target = _normalized_name(player, "player")
    rival_target = _normalized_name(rival, "rival")
    selected = (
        record
        for record in records
        if record.get("player_key") == player_target
        and record.get("rival_key") == rival_target
    )
    return filter_by_league(selected, league) if league is not None else _copy_sorted(selected)


def head_to_head(
    records: Iterable[dict[str, Any]],
    player_a: str,
    player_b: str,
    league: str | None = None,
) -> list[dict[str, Any]]:
    """Select both perspective directions between two players."""
    key_a = _normalized_name(player_a, "player_a")
    key_b = _normalized_name(player_b, "player_b")
    selected = (
        record
        for record in records
        if (
            record.get("player_key") == key_a
            and record.get("rival_key") == key_b
        )
        or (
            record.get("player_key") == key_b
            and record.get("rival_key") == key_a
        )
    )
    return filter_by_league(selected, league) if league is not None else _copy_sorted(selected)


def _parse_time(value: datetime | str, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{label} must be a valid ISO 8601 datetime")
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid ISO 8601 datetime") from exc
    else:
        raise ValueError(f"{label} must be a datetime, ISO 8601 string or None")

    # Naive values are explicitly interpreted as UTC, never as system-local time.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def filter_by_time(
    records: Iterable[dict[str, Any]],
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    *,
    field: str = "timestamp_utc",
) -> list[dict[str, Any]]:
    """Apply inclusive UTC-normalized bounds; naive bounds mean UTC."""
    if not isinstance(field, str) or not field:
        raise ValueError("field must be a non-empty string")
    start_time = _parse_time(start, "start") if start is not None else None
    end_time = _parse_time(end, "end") if end is not None else None
    if start_time is not None and end_time is not None and start_time > end_time:
        raise ValueError("start must not be later than end")
    if start_time is None and end_time is None:
        return _copy_sorted(records)

    selected = []
    for record in records:
        raw_timestamp = record.get(field)
        try:
            timestamp = _parse_time(raw_timestamp, field)
        except ValueError:
            continue
        if start_time is not None and timestamp < start_time:
            continue
        if end_time is not None and timestamp > end_time:
            continue
        selected.append(record)
    return _copy_sorted(selected)


def latest_matches(
    records: Iterable[dict[str, Any]],
    limit: int,
    player: str | None = None,
    league: str | None = None,
) -> list[dict[str, Any]]:
    """Return the latest N perspectives, ascending within the result."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be an integer greater than or equal to zero")
    selected: Iterable[dict[str, Any]] = records
    if player is not None:
        selected = player_history(selected, player)
    if league is not None:
        selected = filter_by_league(selected, league)
    ordered = _copy_sorted(selected)
    if limit == 0:
        return []
    return [dict(record) for record in ordered[-limit:]]


def duplicate_perspective_ids(records: Iterable[dict[str, Any]]) -> list[str]:
    """Return each non-empty textual perspective ID occurring more than once."""
    counts = Counter(
        value
        for record in records
        if isinstance((value := record.get("perspective_id")), str) and value
    )
    return sorted(value for value, count in counts.items() if count > 1)
