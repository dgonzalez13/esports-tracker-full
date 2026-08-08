"""Rank possible upcoming matches inside tracked five-player groups.

The module intentionally exposes an *estimated win percentage*, not a calibrated
probability.  It uses only information that already exists in normalized match
history and never looks at a future result/schedule.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, TypedDict

from selected_players import TrackedPlayer, excluded_player_keys, is_operational_record


RECENT_PLAYER_WINDOW = 24
RECENT_H2H_WINDOW = 20
MIN_ESTIMATED_WIN_PCT = 65.0


class UpcomingPrediction(TypedDict):
    league: str
    group_index: int
    player_a: str
    player_b: str
    predicted_player: str
    opponent: str
    estimated_win_pct: float
    confidence: str
    h2h_matches: int
    h2h_win_pct: float
    recent_h2h_matches: int
    recent_h2h_win_pct: float
    recent_player_matches: int
    recent_player_win_pct: float
    recent_opponent_matches: int
    recent_opponent_loss_pct: float
    overall_player_matches: int
    overall_player_win_pct: float
    overall_opponent_matches: int
    overall_opponent_loss_pct: float


__all__ = [
    "RECENT_PLAYER_WINDOW",
    "RECENT_H2H_WINDOW",
    "MIN_ESTIMATED_WIN_PCT",
    "UpcomingPrediction",
    "calculate_upcoming_predictions",
]


def _valid_result_rows(records: Iterable[dict[str, Any]], excluded_keys) -> list[dict[str, Any]]:
    rows = []
    for source in records:
        if not is_operational_record(source, excluded_keys):
            continue
        if source.get("result") not in {"V", "E", "D"}:
            continue
        league = source.get("league")
        player_key = source.get("player_key")
        rival_key = source.get("rival_key")
        if not all(isinstance(value, str) and value.strip() for value in (league, player_key, rival_key)):
            continue
        rows.append(dict(source))
    rows.sort(key=lambda row: (
        str(row.get("timestamp_utc") or row.get("timestamp") or ""),
        str(row.get("match_id", "")), str(row.get("perspective_id", "")),
    ))
    return rows


def _pct(rows: list[dict[str, Any]], result: str) -> float:
    if not rows:
        return 0.0
    return round(sum(row.get("result") == result for row in rows) / len(rows) * 100, 2)


def _shrunk(pct: float, sample: int, prior_matches: int) -> float:
    """Shrink unstable percentages towards 50 without inventing match records."""
    if sample <= 0:
        return 50.0
    return (float(pct) * sample + 50.0 * prior_matches) / (sample + prior_matches)


def _player_rows(rows, league: str, player_key: str) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("league", "")).strip().upper() == league
        and row.get("player_key") == player_key
    ]


def _h2h_rows(rows, league: str, player_key: str, rival_key: str) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("league", "")).strip().upper() == league
        and row.get("player_key") == player_key
        and row.get("rival_key") == rival_key
    ]


def _estimate_side(rows, league: str, player_key: str, rival_key: str) -> dict[str, Any]:
    player_history = _player_rows(rows, league, player_key)
    rival_history = _player_rows(rows, league, rival_key)
    recent_player = player_history[-RECENT_PLAYER_WINDOW:]
    recent_rival = rival_history[-RECENT_PLAYER_WINDOW:]

    h2h = _h2h_rows(rows, league, player_key, rival_key)
    recent_h2h = h2h[-RECENT_H2H_WINDOW:]

    h2h_win = _pct(h2h, "V")
    recent_h2h_win = _pct(recent_h2h, "V")
    recent_player_win = _pct(recent_player, "V")
    recent_rival_loss = _pct(recent_rival, "D")
    overall_player_win = _pct(player_history, "V")
    overall_rival_loss = _pct(rival_history, "D")

    h2h_component = _shrunk(h2h_win, len(h2h), 12)
    recent_h2h_component = _shrunk(recent_h2h_win, len(recent_h2h), 6)
    recent_form_component = (
        _shrunk(recent_player_win, len(recent_player), 8)
        + _shrunk(recent_rival_loss, len(recent_rival), 8)
    ) / 2
    overall_component = (
        _shrunk(overall_player_win, len(player_history), 40)
        + _shrunk(overall_rival_loss, len(rival_history), 40)
    ) / 2

    estimate = (
        h2h_component * 0.40
        + recent_h2h_component * 0.25
        + recent_form_component * 0.25
        + overall_component * 0.10
    )

    if len(h2h) >= 20 and len(recent_player) >= 12 and len(recent_rival) >= 12:
        confidence = "HIGH"
    elif len(h2h) >= 10 and len(recent_player) >= 8 and len(recent_rival) >= 8:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "estimated_win_pct": round(estimate, 2),
        "confidence": confidence,
        "h2h_matches": len(h2h),
        "h2h_win_pct": h2h_win,
        "recent_h2h_matches": len(recent_h2h),
        "recent_h2h_win_pct": recent_h2h_win,
        "recent_player_matches": len(recent_player),
        "recent_player_win_pct": recent_player_win,
        "recent_opponent_matches": len(recent_rival),
        "recent_opponent_loss_pct": recent_rival_loss,
        "overall_player_matches": len(player_history),
        "overall_player_win_pct": overall_player_win,
        "overall_opponent_matches": len(rival_history),
        "overall_opponent_loss_pct": overall_rival_loss,
    }


def _groups(tracked_players: Iterable[TrackedPlayer]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for source in tracked_players:
        if not source.get("tracked") or not source.get("bettable", True):
            continue
        league = str(source.get("league", "")).strip().upper()
        player = str(source.get("player", "")).strip()
        player_key = str(source.get("player_key", "")).strip()
        if not league or not player or not player_key:
            continue
        group_index = int(source.get("group_index", 0))
        groups.setdefault((league, group_index), []).append(dict(source))
    return groups


def calculate_upcoming_predictions(
    records: Iterable[dict[str, Any]],
    tracked_players: Iterable[TrackedPlayer],
    *,
    min_estimated_win_pct: float = MIN_ESTIMATED_WIN_PCT,
    excluded_keys: set[tuple[str, str]] | None = None,
) -> list[UpcomingPrediction]:
    """Rank high-estimate possible pairings among players in the same tracked group."""
    if isinstance(min_estimated_win_pct, bool) or not isinstance(min_estimated_win_pct, (int, float)):
        raise ValueError("min_estimated_win_pct must be numeric")
    threshold = float(min_estimated_win_pct)
    if threshold < 50 or threshold > 100:
        raise ValueError("min_estimated_win_pct must be between 50 and 100")

    tracked = list(tracked_players)
    excluded = excluded_player_keys(tracked) if excluded_keys is None else excluded_keys
    rows = _valid_result_rows(records, excluded)
    predictions: list[UpcomingPrediction] = []

    for (league, group_index), players in sorted(_groups(tracked).items()):
        # Identity de-duplication is defensive; load_tracked_players already canonicalizes it.
        unique = {(row["league"], row["player_key"]): row for row in players}
        ordered = sorted(unique.values(), key=lambda row: (row["player"].casefold(), row["player_key"]))
        for player_a, player_b in combinations(ordered, 2):
            side_a = _estimate_side(rows, league, player_a["player_key"], player_b["player_key"])
            side_b = _estimate_side(rows, league, player_b["player_key"], player_a["player_key"])
            if side_b["estimated_win_pct"] > side_a["estimated_win_pct"]:
                winner, opponent, metrics = player_b, player_a, side_b
            else:
                winner, opponent, metrics = player_a, player_b, side_a

            if metrics["estimated_win_pct"] < threshold:
                continue
            # Sparse H2H is reflected in confidence instead of being an automatic rejection.
            # Only estimates with MEDIUM/HIGH confidence are surfaced.
            if metrics["confidence"] not in {"HIGH", "MEDIUM"}:
                continue

            predictions.append({
                "league": league,
                "group_index": group_index,
                "player_a": player_a["player"],
                "player_b": player_b["player"],
                "predicted_player": winner["player"],
                "opponent": opponent["player"],
                **metrics,
            })

    confidence_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    predictions.sort(key=lambda row: (
        -row["estimated_win_pct"], confidence_rank.get(row["confidence"], 9),
        row["league"], row["group_index"], row["predicted_player"].casefold(),
        row["opponent"].casefold(),
    ))
    return predictions
