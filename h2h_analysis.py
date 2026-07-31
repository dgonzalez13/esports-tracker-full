"""Pure directional head-to-head analysis over normalized perspectives."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, TypedDict

from historical_analysis import calculate_player_stats
from history_query import (
    EADRIATIC_HISTORY_PATH,
    GT_HISTORY_PATH,
    filter_by_league,
    filter_by_time,
    load_all_history,
    player_vs_rival,
)
from match_history import clean_name
from temporal_analysis import calculate_temporal_window


DEFAULT_H2H_WINDOW = 20
DEFAULT_H2H_TREND_THRESHOLD = 5.0


class H2HStats(TypedDict):
    """Exact historical statistics for one directional H2H relation."""

    league: str | None
    player: str
    rival: str
    played: int
    wins: int
    draws: int
    losses: int
    win_pct: float
    draw_pct: float
    loss_pct: float
    sequence: str
    first_match_date: str | None
    last_match_date: str | None


class H2HRecentStats(TypedDict):
    """Exact recent-window statistics for one directional H2H relation."""

    league: str | None
    player: str
    rival: str
    window: int
    available: int
    window_complete: bool
    wins: int
    draws: int
    losses: int
    win_pct: float
    draw_pct: float
    loss_pct: float
    sequence: str
    current_streak_result: str | None
    current_streak: int
    first_match_date: str | None
    last_match_date: str | None


class H2HComparison(TypedDict):
    """Exact comparison between recent and historical directional H2H."""

    league: str | None
    player: str
    rival: str
    window: int
    recent_available: int
    historical_played: int
    historical_win_pct: float
    recent_win_pct: float
    win_pct_delta: float
    historical_draw_pct: float
    recent_draw_pct: float
    draw_pct_delta: float
    historical_loss_pct: float
    recent_loss_pct: float
    loss_pct_delta: float
    trend: str | None
    sample_status: str


__all__ = [
    "DEFAULT_H2H_WINDOW",
    "DEFAULT_H2H_TREND_THRESHOLD",
    "H2HStats",
    "H2HRecentStats",
    "H2HComparison",
    "empty_h2h_stats",
    "calculate_h2h_stats",
    "calculate_recent_h2h",
    "compare_recent_h2h_to_history",
    "calculate_all_h2h",
    "load_all_h2h",
]


def _league_name(league: str | None) -> str | None:
    if league is None:
        return None
    if not isinstance(league, str) or not league.strip():
        raise ValueError("league must be a non-empty string or None")
    return league.strip().upper()


def _names(player: str, rival: str) -> tuple[str, str]:
    if not isinstance(player, str) or not player.strip():
        raise ValueError("player must be a non-empty string")
    if not isinstance(rival, str) or not rival.strip():
        raise ValueError("rival must be a non-empty string")
    return clean_name(player), clean_name(rival)


def _validate_window(window: int) -> int:
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("window must be an integer greater than zero")
    return window


def _validate_threshold(threshold: float) -> float:
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("trend_threshold must be a non-negative number")
    value = float(threshold)
    if value < 0:
        raise ValueError("trend_threshold must be a non-negative number")
    return value


def _validate_minimum(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("min_historical_matches must be an integer greater than or equal to one")
    return value


def empty_h2h_stats(
    player: str,
    rival: str,
    league: str | None = None,
) -> H2HStats:
    """Return an exact zero-value directional H2H result."""
    player_name, rival_name = _names(player, rival)
    return {
        "league": _league_name(league),
        "player": player_name,
        "rival": rival_name,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "win_pct": 0.0,
        "draw_pct": 0.0,
        "loss_pct": 0.0,
        "sequence": "",
        "first_match_date": None,
        "last_match_date": None,
    }


def calculate_h2h_stats(
    records: Iterable[dict[str, Any]],
    player: str,
    rival: str,
    league: str | None = None,
) -> H2HStats:
    """Calculate exact historical stats for player -> rival only."""
    player_name, rival_name = _names(player, rival)
    history = player_vs_rival(records, player_name, rival_name, league=league)
    valid = [record for record in history if record.get("result") in {"V", "E", "D"}]
    if not valid:
        return empty_h2h_stats(player_name, rival_name, league)

    stats = calculate_player_stats(valid, player_name, league=league)
    display_rival = valid[-1].get("rival")
    if not isinstance(display_rival, str) or not display_rival.strip():
        display_rival = rival_name
    return {
        "league": stats["league"],
        "player": stats["player"],
        "rival": display_rival.strip(),
        "played": stats["played"],
        "wins": stats["wins"],
        "draws": stats["draws"],
        "losses": stats["losses"],
        "win_pct": stats["win_pct"],
        "draw_pct": stats["draw_pct"],
        "loss_pct": stats["loss_pct"],
        "sequence": "".join(record["result"] for record in valid),
        "first_match_date": stats["first_match_date"],
        "last_match_date": stats["last_match_date"],
    }


def calculate_recent_h2h(
    records: Iterable[dict[str, Any]],
    player: str,
    rival: str,
    window: int = DEFAULT_H2H_WINDOW,
    league: str | None = None,
) -> H2HRecentStats:
    """Calculate the latest N valid directional H2H perspectives."""
    player_name, rival_name = _names(player, rival)
    window = _validate_window(window)
    history = player_vs_rival(records, player_name, rival_name, league=league)
    recent = calculate_temporal_window(history, player_name, window, league=league)
    display_rival = history[-1].get("rival") if history else rival_name
    if not isinstance(display_rival, str) or not display_rival.strip():
        display_rival = rival_name
    return {
        "league": recent["league"],
        "player": recent["player"],
        "rival": display_rival.strip(),
        "window": window,
        "available": recent["available"],
        "window_complete": recent["available"] >= window,
        "wins": recent["wins"],
        "draws": recent["draws"],
        "losses": recent["losses"],
        "win_pct": recent["win_pct"],
        "draw_pct": recent["draw_pct"],
        "loss_pct": recent["loss_pct"],
        "sequence": recent["sequence"],
        "current_streak_result": recent["current_streak_result"],
        "current_streak": recent["current_streak"],
        "first_match_date": recent["first_match_date"],
        "last_match_date": recent["last_match_date"],
    }


def _trend(delta: float, available: int, threshold: float) -> str | None:
    if available == 0:
        return None
    if delta > 0 and delta >= threshold:
        return "UP"
    if delta < 0 and delta <= -threshold:
        return "DOWN"
    return "STABLE"


def _sample_status(available: int, window: int) -> str:
    if available == 0:
        return "EMPTY"
    if available < window:
        return "LOW_SAMPLE"
    return "COMPLETE"


def compare_recent_h2h_to_history(
    records: Iterable[dict[str, Any]],
    player: str,
    rival: str,
    window: int = DEFAULT_H2H_WINDOW,
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_H2H_TREND_THRESHOLD,
) -> H2HComparison:
    """Compare recent and historical directional H2H percentages."""
    materialized = list(records)
    window = _validate_window(window)
    threshold = _validate_threshold(trend_threshold)
    historical = calculate_h2h_stats(materialized, player, rival, league=league)
    recent = calculate_recent_h2h(materialized, player, rival, window, league=league)
    win_delta = round(recent["win_pct"] - historical["win_pct"], 2)
    draw_delta = round(recent["draw_pct"] - historical["draw_pct"], 2)
    loss_delta = round(recent["loss_pct"] - historical["loss_pct"], 2)
    return {
        "league": historical["league"],
        "player": historical["player"],
        "rival": historical["rival"],
        "window": window,
        "recent_available": recent["available"],
        "historical_played": historical["played"],
        "historical_win_pct": historical["win_pct"],
        "recent_win_pct": recent["win_pct"],
        "win_pct_delta": win_delta,
        "historical_draw_pct": historical["draw_pct"],
        "recent_draw_pct": recent["draw_pct"],
        "draw_pct_delta": draw_delta,
        "historical_loss_pct": historical["loss_pct"],
        "recent_loss_pct": recent["loss_pct"],
        "loss_pct_delta": loss_delta,
        "trend": _trend(win_delta, recent["available"], threshold),
        "sample_status": _sample_status(recent["available"], window),
    }


def calculate_all_h2h(
    records: Iterable[dict[str, Any]],
    window: int = DEFAULT_H2H_WINDOW,
    league: str | None = None,
    *,
    min_historical_matches: int = 1,
    trend_threshold: float = DEFAULT_H2H_TREND_THRESHOLD,
) -> list[H2HComparison]:
    """Calculate every existing directional league/player/rival relation."""
    window = _validate_window(window)
    minimum = _validate_minimum(min_historical_matches)
    threshold = _validate_threshold(trend_threshold)
    ordered = filter_by_league(records, league) if league is not None else filter_by_time(records)

    identities: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for record in ordered:
        values = (
            record.get("league"), record.get("player"), record.get("player_key"),
            record.get("rival"), record.get("rival_key"),
        )
        if not all(isinstance(value, str) and value.strip() for value in values):
            continue
        record_league, player, player_key, rival, rival_key = values
        identities[
            (record_league.strip().casefold(), player_key, rival_key)
        ] = (record_league.strip(), player.strip(), rival.strip())

    rows = []
    for _, (record_league, player, rival) in sorted(identities.items()):
        comparison = compare_recent_h2h_to_history(
            ordered,
            player,
            rival,
            window,
            league=record_league,
            trend_threshold=threshold,
        )
        if comparison["historical_played"] >= minimum:
            rows.append(comparison)
    return sorted(
        rows,
        key=lambda row: (
            (row["league"] or "").casefold(),
            row["player"].casefold(),
            row["rival"].casefold(),
        ),
    )


def load_all_h2h(
    gt_path: str | Path = GT_HISTORY_PATH,
    eadriatic_path: str | Path = EADRIATIC_HISTORY_PATH,
    window: int = DEFAULT_H2H_WINDOW,
    league: str | None = None,
    *,
    min_historical_matches: int = 1,
    trend_threshold: float = DEFAULT_H2H_TREND_THRESHOLD,
) -> list[H2HComparison]:
    """Load through history_query and delegate all H2H analysis."""
    records = load_all_history(gt_path=gt_path, eadriatic_path=eadriatic_path)
    return calculate_all_h2h(
        records,
        window,
        league=league,
        min_historical_matches=min_historical_matches,
        trend_threshold=trend_threshold,
    )
