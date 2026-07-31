"""Pure historical statistics built from normalized match perspectives."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypedDict

from history_query import (
    EADRIATIC_HISTORY_PATH,
    GT_HISTORY_PATH,
    filter_by_league,
    filter_by_time,
    load_all_history,
    player_history,
)
from match_history import clean_name


__all__ = [
    "PlayerHistoricalStats",
    "empty_player_stats",
    "calculate_player_stats",
    "calculate_historical_stats",
    "load_historical_stats",
]


class PlayerHistoricalStats(TypedDict):
    """Stable dictionary model returned for one player's historical metrics."""

    league: str | None
    player: str
    played: int
    wins: int
    draws: int
    losses: int
    win_pct: float
    draw_pct: float
    loss_pct: float
    current_streak_result: str | None
    current_streak: int
    best_win_streak: int
    best_loss_streak: int
    first_match_date: str | None
    last_match_date: str | None


def _build_player_stats(
    *,
    league: str | None,
    player: str,
    played: int,
    wins: int,
    draws: int,
    losses: int,
    win_pct: float,
    draw_pct: float,
    loss_pct: float,
    current_streak_result: str | None,
    current_streak: int,
    best_win_streak: int,
    best_loss_streak: int,
    first_match_date: str | None,
    last_match_date: str | None,
) -> PlayerHistoricalStats:
    """Construct the single public statistics shape used by every code path."""
    return {
        "league": league,
        "player": player,
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_pct": win_pct,
        "draw_pct": draw_pct,
        "loss_pct": loss_pct,
        "current_streak_result": current_streak_result,
        "current_streak": current_streak,
        "best_win_streak": best_win_streak,
        "best_loss_streak": best_loss_streak,
        "first_match_date": first_match_date,
        "last_match_date": last_match_date,
    }


def empty_player_stats(player: str, league: str | None = None) -> PlayerHistoricalStats:
    """Return the stable zero-value result used for a player without matches."""
    display_name = clean_name(player)
    league_name = league.strip().upper() if isinstance(league, str) and league.strip() else None
    return _build_player_stats(
        league=league_name,
        player=display_name,
        played=0,
        wins=0,
        draws=0,
        losses=0,
        win_pct=0.0,
        draw_pct=0.0,
        loss_pct=0.0,
        current_streak_result=None,
        current_streak=0,
        best_win_streak=0,
        best_loss_streak=0,
        first_match_date=None,
        last_match_date=None,
    )


def _date_from_record(record: dict[str, Any]) -> str | None:
    for field in ("timestamp_utc", "timestamp"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).date().isoformat()
    return None


def _best_streak(results: Iterable[str], target: str) -> int:
    best = 0
    current = 0
    for result in results:
        if result == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def calculate_player_stats(
    records: Iterable[dict[str, Any]],
    player: str,
    league: str | None = None,
) -> PlayerHistoricalStats:
    """Calculate one player's exact W/E/D totals, percentages and streaks."""
    history = player_history(records, player, league=league)
    valid = [record for record in history if record.get("result") in {"V", "E", "D"}]
    if not valid:
        return empty_player_stats(player, league)

    display_name = valid[-1].get("player")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = clean_name(player)
    else:
        display_name = display_name.strip()
    league_name = valid[-1].get("league")
    if not isinstance(league_name, str) or not league_name.strip():
        league_name = league.strip().upper() if isinstance(league, str) and league.strip() else None
    else:
        league_name = league_name.strip().upper()

    results = [record["result"] for record in valid]
    played = len(results)
    wins = results.count("V")
    draws = results.count("E")
    losses = results.count("D")
    current_result = results[-1]
    current_streak = 0
    for result in reversed(results):
        if result != current_result:
            break
        current_streak += 1

    dates = [date for record in valid if (date := _date_from_record(record)) is not None]
    return _build_player_stats(
        league=league_name,
        player=display_name,
        played=played,
        wins=wins,
        draws=draws,
        losses=losses,
        win_pct=round(wins / played * 100, 2),
        draw_pct=round(draws / played * 100, 2),
        loss_pct=round(losses / played * 100, 2),
        current_streak_result=current_result,
        current_streak=current_streak,
        best_win_streak=_best_streak(results, "V"),
        best_loss_streak=_best_streak(results, "D"),
        first_match_date=min(dates) if dates else None,
        last_match_date=max(dates) if dates else None,
    )


def calculate_historical_stats(
    records: Iterable[dict[str, Any]], league: str | None = None
) -> list[PlayerHistoricalStats]:
    """Calculate statistics for every distinct league/player identity."""
    ordered = filter_by_league(records, league) if league is not None else filter_by_time(records)
    identities: dict[tuple[str, str], str] = {}
    for record in ordered:
        player_key = record.get("player_key")
        player = record.get("player")
        record_league = record.get("league")
        if not all(isinstance(value, str) and value.strip() for value in (player_key, player, record_league)):
            continue
        identities[(record_league.strip().casefold(), player_key)] = player.strip()

    rows = [
        calculate_player_stats(ordered, player, league=league_key)
        for (league_key, _), player in sorted(identities.items())
    ]
    return sorted(rows, key=lambda row: ((row["league"] or "").casefold(), row["player"].casefold()))
def load_historical_stats(
    gt_path: str | Path = GT_HISTORY_PATH,
    eadriatic_path: str | Path = EADRIATIC_HISTORY_PATH,
    league: str | None = None,
) -> list[PlayerHistoricalStats]:
    """Load histories through history_query and calculate all player rows."""
    return calculate_historical_stats(
        load_all_history(gt_path=gt_path, eadriatic_path=eadriatic_path),
        league=league,
    )
