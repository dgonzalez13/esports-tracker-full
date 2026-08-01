"""Canonical parser for tracked and selected players."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, TypedDict

from match_history import name_key


class TrackedPlayer(TypedDict):
    league: str
    player: str
    player_key: str
    tracked: bool
    selected: bool


__all__ = [
    "TrackedPlayer", "parse_tracked_player_line", "load_tracked_players",
    "tracked_player_keys", "selected_player_keys",
]


def parse_tracked_player_line(line: str) -> TrackedPlayer | None:
    if not isinstance(line, str):
        raise ValueError("tracked player line must be a string")
    value = line.strip()
    if not value:
        return None
    if "|" not in value:
        raise ValueError("tracked player line must use LIGA|Nombre format")
    league, player = value.split("|", 1)
    league = league.strip().upper()
    player = player.strip()
    selected = player.endswith("*")
    if selected:
        player = player[:-1].strip()
    if not league:
        raise ValueError("tracked player league must not be empty")
    if not player:
        raise ValueError("tracked player name must not be empty")
    return {
        "league": league,
        "player": player,
        "player_key": name_key(player),
        "tracked": True,
        "selected": selected,
    }


def load_tracked_players(path: str | Path) -> list[TrackedPlayer]:
    source = Path(path)
    if not source.exists():
        return []
    players: list[TrackedPlayer] = []
    positions: dict[tuple[str, str], int] = {}
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                entry = parse_tracked_player_line(line)
            except ValueError as exc:
                raise ValueError(f"invalid tracked player at line {line_number}: {exc}") from exc
            if entry is None:
                continue
            identity = (entry["league"], entry["player_key"])
            if identity in positions:
                existing = players[positions[identity]]
                existing["selected"] = existing["selected"] or entry["selected"]
            else:
                positions[identity] = len(players)
                players.append(entry)
    return players


def tracked_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {(row["league"], row["player_key"]) for row in players if row.get("tracked")}


def selected_player_keys(players: Iterable[TrackedPlayer]) -> set[tuple[str, str]]:
    return {(row["league"], row["player_key"]) for row in players if row.get("selected")}
