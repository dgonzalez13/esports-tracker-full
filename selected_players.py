"""Canonical parser for tracked and selected players."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, TypedDict

from match_history import name_key


class TrackedPlayer(TypedDict):
    league: str
    player: str
    player_key: str
    tracked: bool
    selected: bool
    bettable: bool


class TrackedPlayerEntry(TrackedPlayer, total=False):
    empty_slot: bool
    group_index: int


class CoincidentConfig(TypedDict):
    selected_keys: set[tuple[str, str]]
    excluded_keys: set[tuple[str, str]]


__all__ = [
    "TrackedPlayer", "TrackedPlayerEntry", "parse_tracked_player_line", "load_tracked_players",
    "tracked_player_keys", "bettable_player_keys", "excluded_player_keys",
    "selected_player_keys", "is_operational_record",
    "CoincidentConfig", "load_coincident_config",
]



_COINCIDENT_SELECT = "@COINCIDENT_SELECT||"
_COINCIDENT_EXCLUDE = "@COINCIDENT_EXCLUDE||"


def _parse_coincident_identity(value: str) -> tuple[str, str]:
    item = value.strip()
    if "|" not in item:
        raise ValueError("coincident identity must use LIGA|Nombre format")
    league, player = item.split("|", 1)
    league = league.strip().upper()
    player = player.strip()
    if not league or not player:
        raise ValueError("coincident identity must include league and player")
    return league, name_key(player)


def load_coincident_config(path: str | Path) -> CoincidentConfig:
    source = Path(path)
    config: CoincidentConfig = {"selected_keys": set(), "excluded_keys": set()}
    if not source.exists():
        return config
    with source.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            value = raw.strip()
            target = None
            payload = ""
            if value.startswith(_COINCIDENT_SELECT):
                target = config["selected_keys"]
                payload = value[len(_COINCIDENT_SELECT):]
            elif value.startswith(_COINCIDENT_EXCLUDE):
                target = config["excluded_keys"]
                payload = value[len(_COINCIDENT_EXCLUDE):]
            else:
                continue
            if not payload.strip():
                continue
            for item in payload.split(","):
                if not item.strip():
                    continue
                try:
                    target.add(_parse_coincident_identity(item))
                except ValueError as exc:
                    raise ValueError(f"invalid coincident directive at line {line_number}: {exc}") from exc
    return config

def parse_tracked_player_line(line: str) -> TrackedPlayerEntry | None:
    if not isinstance(line, str):
        raise ValueError("tracked player line must be a string")
    value = line.strip()
    if not value:
        return None
    if value.startswith("@COINCIDENT_"):
        return None
    if "|" not in value:
        raise ValueError("tracked player line must use LIGA|Nombre format")
    league, player = value.split("|", 1)
    league = league.strip().upper()
    player = player.strip()
    excluded = player.endswith("*")
    if excluded:
        player = player[:-1].strip()
    if not league:
        raise ValueError("tracked player league must not be empty")
    if not player:
        return {
            "league": league, "player": "", "player_key": "",
            "tracked": False, "selected": False, "bettable": False,
            "empty_slot": True,
        }
    return {
        "league": league,
        "player": player,
        "player_key": name_key(player),
        "tracked": True, "selected": False, "bettable": not excluded,
        "empty_slot": False,
    }


def load_tracked_players(path: str | Path) -> list[TrackedPlayerEntry]:
    source = Path(path)
    if not source.exists():
        return []
    players: list[TrackedPlayerEntry] = []
    positions: dict[tuple[str, str], int] = {}
    league_positions: dict[str, int] = {}
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                entry = parse_tracked_player_line(line)
            except ValueError as exc:
                raise ValueError(f"invalid tracked player at line {line_number}: {exc}") from exc
            if entry is None:
                continue
            league = entry["league"]
            position = league_positions.get(league, 0)
            entry["group_index"] = position // 5
            league_positions[league] = position + 1
            # Empty entries are positions, not identities: never deduplicate them.
            if entry.get("empty_slot"):
                players.append(entry)
                continue
            identity = (entry["league"], entry["player_key"])
            if identity in positions:
                existing = players[positions[identity]]
                existing["bettable"] = existing["bettable"] and entry["bettable"]
            else:
                positions[identity] = len(players)
                players.append(entry)
    return players


def tracked_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {(row["league"], row["player_key"]) for row in players if row.get("tracked")}


def bettable_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {
        (row["league"], row["player_key"])
        for row in players if row.get("tracked") and row.get("bettable", True)
    }


def excluded_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {
        (row["league"], row["player_key"])
        for row in players if row.get("tracked") and not row.get("bettable", True)
    }


def selected_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {(row["league"], row["player_key"]) for row in players if row.get("selected")}


def is_operational_record(
    record: Any, excluded_keys: set[tuple[str, str]] | None = None,
) -> bool:
    """Return whether a normalized perspective is safe for operational use."""
    if not isinstance(record, dict):
        return False
    league = record.get("league")
    player_key = record.get("player_key")
    rival_key = record.get("rival_key")
    if not all(isinstance(value, str) and value.strip() for value in (
        league, player_key, rival_key,
    )):
        return False
    league = league.strip().upper()
    excluded = excluded_keys or set()
    return (
        (league, player_key) not in excluded
        and (league, rival_key) not in excluded
    )
