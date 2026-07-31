"""Pure temporal-window analysis over normalized match perspectives."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, TypedDict

from historical_analysis import calculate_historical_stats, calculate_player_stats
from history_query import (
    EADRIATIC_HISTORY_PATH,
    GT_HISTORY_PATH,
    load_all_history,
    player_history,
    player_vs_rival,
)
from match_history import clean_name


DEFAULT_TREND_THRESHOLD = 5.0


class TemporalWindowStats(TypedDict):
    """Exact public model for one player's temporal window."""

    league: str | None
    player: str
    window: int
    available: int
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


class RecentHistoryComparison(TypedDict):
    """Exact public model comparing a recent window with full history."""

    league: str | None
    player: str
    window: int
    recent_available: int
    historical_played: int
    recent_win_pct: float
    historical_win_pct: float
    win_pct_delta: float
    recent_draw_pct: float
    historical_draw_pct: float
    draw_pct_delta: float
    recent_loss_pct: float
    historical_loss_pct: float
    loss_pct_delta: float


__all__ = [
    "DEFAULT_TREND_THRESHOLD",
    "TemporalWindowStats",
    "RecentHistoryComparison",
    "empty_temporal_window",
    "calculate_temporal_window",
    "calculate_player_windows",
    "calculate_all_player_windows",
    "compare_recent_to_history",
    "load_temporal_windows",
    # Compatibility API retained from the first TASK-003 implementation.
    "calculate_recent_form",
    "calculate_recent_vs_rival",
    "calculate_temporal_windows",
    "calculate_all_recent_forms",
    "load_recent_forms",
]


def _validate_window(window: int) -> int:
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("window must be an integer greater than zero")
    return window


def _validated_windows(windows: Iterable[int]) -> list[int]:
    return sorted({_validate_window(window) for window in windows})


def _league_name(league: str | None) -> str | None:
    if league is None:
        return None
    if not isinstance(league, str) or not league.strip():
        raise ValueError("league must be a non-empty string or None")
    return league.strip().upper()


def _validate_threshold(threshold: float) -> float:
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("trend_threshold must be a non-negative number")
    value = float(threshold)
    if value < 0:
        raise ValueError("trend_threshold must be a non-negative number")
    return value


def empty_temporal_window(
    player: str,
    window: int,
    league: str | None = None,
) -> TemporalWindowStats:
    """Return the exact zero-value temporal-window shape."""
    return {
        "league": _league_name(league),
        "player": clean_name(player),
        "window": _validate_window(window),
        "available": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "win_pct": 0.0,
        "draw_pct": 0.0,
        "loss_pct": 0.0,
        "sequence": "",
        "current_streak_result": None,
        "current_streak": 0,
        "first_match_date": None,
        "last_match_date": None,
    }


def _window_from_history(
    history: Iterable[dict[str, Any]],
    player: str,
    window: int,
    league: str | None,
) -> TemporalWindowStats:
    valid = [record for record in history if record.get("result") in {"V", "E", "D"}]
    recent = valid[-window:]
    if not recent:
        return empty_temporal_window(player, window, league)

    stats = calculate_player_stats(recent, player, league=league)
    return {
        "league": stats["league"],
        "player": stats["player"],
        "window": window,
        "available": stats["played"],
        "wins": stats["wins"],
        "draws": stats["draws"],
        "losses": stats["losses"],
        "win_pct": stats["win_pct"],
        "draw_pct": stats["draw_pct"],
        "loss_pct": stats["loss_pct"],
        "sequence": "".join(record["result"] for record in recent),
        "current_streak_result": stats["current_streak_result"],
        "current_streak": stats["current_streak"],
        "first_match_date": stats["first_match_date"],
        "last_match_date": stats["last_match_date"],
    }


def calculate_temporal_window(
    records: Iterable[dict[str, Any]],
    player: str,
    window: int,
    league: str | None = None,
) -> TemporalWindowStats:
    """Calculate the latest N valid perspectives after player/league filtering."""
    window = _validate_window(window)
    history = player_history(records, player, league=league)
    return _window_from_history(history, player, window, league)


def calculate_player_windows(
    records: Iterable[dict[str, Any]],
    player: str,
    windows: Iterable[int] = (5, 10, 20),
    league: str | None = None,
) -> list[TemporalWindowStats]:
    """Calculate unique, numerically sorted windows for one player."""
    materialized = list(records)
    requested = _validated_windows(windows)
    return [
        calculate_temporal_window(materialized, player, window, league=league)
        for window in requested
    ]


def calculate_all_player_windows(
    records: Iterable[dict[str, Any]],
    windows: Iterable[int] = (5, 10, 20),
    league: str | None = None,
) -> list[TemporalWindowStats]:
    """Calculate windows for every independent league/player identity."""
    materialized = list(records)
    requested = _validated_windows(windows)
    identities = calculate_historical_stats(materialized, league=league)
    rows = [
        calculate_temporal_window(
            materialized,
            identity["player"],
            window,
            league=identity["league"],
        )
        for identity in identities
        for window in requested
    ]
    return sorted(
        rows,
        key=lambda row: (
            (row["league"] or "").casefold(),
            row["player"].casefold(),
            row["window"],
        ),
    )


def compare_recent_to_history(
    records: Iterable[dict[str, Any]],
    player: str,
    window: int,
    league: str | None = None,
) -> RecentHistoryComparison:
    """Compare recent and historical W/E/D percentages for one player."""
    materialized = list(records)
    recent = calculate_temporal_window(materialized, player, window, league=league)
    historical = calculate_player_stats(materialized, player, league=league)
    return {
        "league": historical["league"],
        "player": historical["player"],
        "window": recent["window"],
        "recent_available": recent["available"],
        "historical_played": historical["played"],
        "recent_win_pct": recent["win_pct"],
        "historical_win_pct": historical["win_pct"],
        "win_pct_delta": round(recent["win_pct"] - historical["win_pct"], 2),
        "recent_draw_pct": recent["draw_pct"],
        "historical_draw_pct": historical["draw_pct"],
        "draw_pct_delta": round(recent["draw_pct"] - historical["draw_pct"], 2),
        "recent_loss_pct": recent["loss_pct"],
        "historical_loss_pct": historical["loss_pct"],
        "loss_pct_delta": round(recent["loss_pct"] - historical["loss_pct"], 2),
    }


def load_temporal_windows(
    gt_path: str | Path = GT_HISTORY_PATH,
    eadriatic_path: str | Path = EADRIATIC_HISTORY_PATH,
    windows: Iterable[int] = (5, 10, 20),
    league: str | None = None,
) -> list[TemporalWindowStats]:
    """Load only through history_query and delegate all window calculation."""
    records = load_all_history(gt_path=gt_path, eadriatic_path=eadriatic_path)
    return calculate_all_player_windows(records, windows=windows, league=league)


# ---------------------------------------------------------------------------
# Compatibility wrappers from the first TASK-003 implementation.
# They intentionally remain additional dictionaries, not the exact models.
# ---------------------------------------------------------------------------

def _trend(delta: float, played: int, threshold: float) -> str | None:
    if played == 0:
        return None
    if delta > 0 and delta >= threshold:
        return "UP"
    if delta < 0 and delta <= -threshold:
        return "DOWN"
    return "STABLE"


def _compat_recent(
    history: Iterable[dict[str, Any]],
    player: str,
    window: int,
    league: str | None,
    threshold: float,
) -> dict[str, Any]:
    materialized = list(history)
    recent = calculate_temporal_window(materialized, player, window, league=league)
    comparison = compare_recent_to_history(materialized, player, window, league=league)
    valid = [record for record in materialized if record.get("result") in {"V", "E", "D"}]
    recent_records = valid[-window:]
    legacy_stats = calculate_player_stats(recent_records, player, league=league)
    return {
        **legacy_stats,
        "window_size": window,
        "available_matches": recent["available"],
        "window_complete": recent["available"] == window,
        "historical_played": comparison["historical_played"],
        "historical_win_pct": comparison["historical_win_pct"],
        "win_pct_delta": comparison["win_pct_delta"],
        "trend": _trend(comparison["win_pct_delta"], recent["available"], threshold),
    }


def calculate_recent_form(
    records: Iterable[dict[str, Any]],
    player: str,
    window: int,
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
) -> dict[str, Any]:
    """Compatibility wrapper returning the original enriched recent form."""
    window = _validate_window(window)
    threshold = _validate_threshold(trend_threshold)
    history = player_history(records, player, league=league)
    return _compat_recent(history, player, window, league, threshold)


def calculate_recent_vs_rival(
    records: Iterable[dict[str, Any]],
    player: str,
    rival: str,
    window: int,
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
) -> dict[str, Any]:
    """Compatibility wrapper for directional recent H2H form."""
    window = _validate_window(window)
    threshold = _validate_threshold(trend_threshold)
    history = player_vs_rival(records, player, rival, league=league)
    return _compat_recent(history, player, window, league, threshold)


def calculate_temporal_windows(
    records: Iterable[dict[str, Any]],
    player: str,
    windows: Iterable[int] = (5, 10),
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
) -> list[dict[str, Any]]:
    """Compatibility wrapper preserving requested order and duplicates."""
    materialized = list(records)
    return [
        calculate_recent_form(
            materialized,
            player,
            window,
            league=league,
            trend_threshold=trend_threshold,
        )
        for window in list(windows)
    ]


def calculate_all_recent_forms(
    records: Iterable[dict[str, Any]],
    window: int,
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
) -> list[dict[str, Any]]:
    """Compatibility wrapper for all league/player identities."""
    materialized = list(records)
    identities = calculate_historical_stats(materialized, league=league)
    return [
        calculate_recent_form(
            materialized,
            identity["player"],
            window,
            league=identity["league"],
            trend_threshold=trend_threshold,
        )
        for identity in identities
    ]


def load_recent_forms(
    window: int,
    gt_path: str | Path = GT_HISTORY_PATH,
    eadriatic_path: str | Path = EADRIATIC_HISTORY_PATH,
    league: str | None = None,
    *,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
) -> list[dict[str, Any]]:
    """Compatibility loader retained from the initial implementation."""
    records = load_all_history(gt_path=gt_path, eadriatic_path=eadriatic_path)
    return calculate_all_recent_forms(
        records,
        window,
        league=league,
        trend_threshold=trend_threshold,
    )
