"""Chronological backward-only matching for selected players."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, TypedDict

from history_query import EADRIATIC_HISTORY_PATH, GT_HISTORY_PATH, load_all_history
from selected_players import TrackedPlayer, load_tracked_players
from current_streaks_v2 import DEFAULT_OPERATIONAL_WINDOW_HOURS, calculate_operational_snapshot


DEFAULT_MAX_COINCIDENT_GAP_MINUTES = 30
MAX_AUTOMATIC_CANDIDATES = 8


class CoincidentPairResults(list):
    """List-compatible pair collection carrying automatic-selection metadata."""

    def __init__(self, values=(), *, eligible_players=0, selected_candidates=0):
        super().__init__(values)
        self.eligible_players = eligible_players
        self.selected_candidates = selected_candidates
        self.candidate_limit = MAX_AUTOMATIC_CANDIDATES


class SelectedPlayerRef(TypedDict):
    league: str
    player: str
    player_key: str


class AutomaticPlayerRef(SelectedPlayerRef, total=False):
    indicator: str
    wins: int
    draws: int
    losses: int
    played: int
    win_pct: float
    loss_pct: float


class CoincidentMatch(TypedDict):
    player_a_league: str
    player_a: str
    player_a_match_id: str
    player_a_timestamp: str
    player_a_result: str
    player_a_rival: str
    player_b_league: str
    player_b: str
    player_b_match_id: str
    player_b_timestamp: str
    player_b_result: str
    player_b_rival: str
    gap_minutes: int
    pair_order: int
    confirmation: str | None


class CoincidentPairAnalysis(TypedDict):
    player_a_league: str
    player_a: str
    player_b_league: str
    player_b: str
    player_a_indicator: str
    player_b_indicator: str
    max_gap_minutes: int
    operational_window_hours: int
    matches: list[CoincidentMatch]


__all__ = [
    "DEFAULT_MAX_COINCIDENT_GAP_MINUTES", "MAX_AUTOMATIC_CANDIDATES",
    "CoincidentPairResults", "SelectedPlayerRef", "CoincidentMatch",
    "CoincidentPairAnalysis", "build_selected_player_refs", "build_automatic_player_refs", "generate_selected_pairs",
    "player_match_history", "match_coincident_pair", "calculate_all_coincident_pairs",
    "load_all_coincident_pairs",
]


def _ref_key(player: SelectedPlayerRef) -> tuple[str, str]:
    return player["league"].strip().upper(), player["player_key"]


def _ref_sort(player: SelectedPlayerRef) -> tuple[str, str, str]:
    return player["league"], player["player"].casefold(), player["player_key"]


def build_selected_player_refs(tracked_players: Iterable[TrackedPlayer]) -> list[SelectedPlayerRef]:
    found: dict[tuple[str, str], SelectedPlayerRef] = {}
    for row in tracked_players:
        if not row.get("selected"):
            continue
        league, player, player_key = row.get("league"), row.get("player"), row.get("player_key")
        if not all(isinstance(value, str) and value.strip() for value in (league, player, player_key)):
            continue
        ref: SelectedPlayerRef = {
            "league": league.strip().upper(), "player": player.strip(), "player_key": player_key,
            "indicator": "NONE", "wins": 0, "draws": 0, "losses": 0,
            "played": 0, "win_pct": 0.0, "loss_pct": 0.0,
        }
        found.setdefault(_ref_key(ref), ref)
    return sorted((dict(row) for row in found.values()), key=_ref_sort)


def _automatic_candidate_sort(row):
    relevant_pct = row["win_pct"] if row["indicator"] == "GREEN" else row["loss_pct"]
    return (
        -(relevant_pct - 50.0), -row["played"], -relevant_pct,
        row["league"], row["player"].casefold(), row["player_key"],
    )


def _eligible_automatic_player_refs(snapshot) -> list[SelectedPlayerRef]:
    found = {}
    for row in snapshot:
        if row.get("played", 0) < 5 or row.get("indicator") not in {"GREEN", "RED"}:
            continue
        ref = {key: row[key] for key in (
            "league", "player", "player_key", "indicator", "wins", "draws",
            "losses", "played", "win_pct", "loss_pct",
        )}
        found.setdefault(_ref_key(ref), ref)
    return sorted((dict(row) for row in found.values()), key=_automatic_candidate_sort)


def build_automatic_player_refs(snapshot) -> list[SelectedPlayerRef]:
    """Return the strongest eligible automatic candidates, capped deterministically."""
    return _eligible_automatic_player_refs(snapshot)[:MAX_AUTOMATIC_CANDIDATES]


def generate_selected_pairs(selected_players: Iterable[SelectedPlayerRef]) -> list[tuple[SelectedPlayerRef, SelectedPlayerRef]]:
    unique: dict[tuple[str, str], SelectedPlayerRef] = {}
    for row in selected_players:
        try:
            unique.setdefault(_ref_key(row), dict(row))
        except (KeyError, AttributeError):
            continue
    ordered = sorted(unique.values(), key=_ref_sort)
    return [(dict(a), dict(b)) for a, b in combinations(ordered, 2)]


def _timestamp(record: dict[str, Any]) -> datetime | None:
    raw = record.get("timestamp_utc") or record.get("timestamp")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_sort(record: dict[str, Any]) -> tuple[datetime, str, str]:
    return _timestamp(record) or datetime.min.replace(tzinfo=timezone.utc), str(record.get("match_id", "")), str(record.get("perspective_id", ""))


def player_match_history(records: Iterable[dict[str, Any]], player: SelectedPlayerRef) -> list[dict[str, Any]]:
    league, player_key = _ref_key(player)
    matches = []
    for source in records:
        if not isinstance(source, dict):
            continue
        source_league = source.get("league")
        if not isinstance(source_league, str) or source_league.strip().upper() != league:
            continue
        if source.get("player_key") != player_key or source.get("result") not in {"V", "E", "D"}:
            continue
        if _timestamp(source) is None:
            continue
        matches.append(dict(source))
    return sorted(matches, key=_event_sort)


def _validate_gap(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("max_gap_minutes must be an integer greater than or equal to zero")
    return value


def _utc_z(record: dict[str, Any]) -> str:
    return (_timestamp(record) or datetime.min.replace(tzinfo=timezone.utc)).isoformat().replace("+00:00", "Z")


def _match_histories(player_a, history_a, player_b, history_b, max_gap_minutes):
    histories = [list(history_a), list(history_b)]
    timeline = []
    for side, history in enumerate(histories):
        for record in history:
            timeline.append((_event_sort(record), side, record))
    timeline.sort(key=lambda item: (item[0][0], item[1], item[0][1], item[0][2]))
    available = [[], []]
    paired = []
    for _, side, current in timeline:
        other = 1 - side
        if not available[other]:
            available[side].append(current)
            continue
        previous = available[other][-1]
        seconds = (_timestamp(current) - _timestamp(previous)).total_seconds()
        gap = int(seconds // 60)
        if seconds < 0 or seconds > max_gap_minutes * 60:
            available[side].append(current)
            continue
        available[other].pop()
        a, b = (current, previous) if side == 0 else (previous, current)
        paired.append((max(_timestamp(a), _timestamp(b)), a, b, gap))
    paired.sort(key=lambda item: (item[0], _event_sort(item[1]), _event_sort(item[2])))
    rows: list[CoincidentMatch] = []
    for order, (_, a, b, gap) in enumerate(paired, 1):
        indicator_a, indicator_b = player_a.get("indicator", "NONE"), player_b.get("indicator", "NONE")
        confirms_a = (indicator_a == "GREEN" and a["result"] == "V") or (indicator_a == "RED" and a["result"] == "D")
        confirms_b = (indicator_b == "GREEN" and b["result"] == "V") or (indicator_b == "RED" and b["result"] == "D")
        confirmation = None
        if confirms_a and confirms_b:
            if indicator_a == indicator_b == "GREEN":
                confirmation = "BOTH_GREEN"
            elif indicator_a == indicator_b == "RED":
                confirmation = "BOTH_RED"
            elif {indicator_a, indicator_b} == {"GREEN", "RED"}:
                confirmation = "MIXED"
        rows.append({
            "player_a_league": player_a["league"], "player_a": player_a["player"],
            "player_a_match_id": str(a.get("match_id", "")), "player_a_timestamp": _utc_z(a),
            "player_a_result": a["result"], "player_a_rival": str(a.get("rival", "")),
            "player_b_league": player_b["league"], "player_b": player_b["player"],
            "player_b_match_id": str(b.get("match_id", "")), "player_b_timestamp": _utc_z(b),
            "player_b_result": b["result"], "player_b_rival": str(b.get("rival", "")),
            "gap_minutes": gap, "pair_order": order, "confirmation": confirmation,
        })
    return {
        "player_a_league": player_a["league"], "player_a": player_a["player"],
        "player_b_league": player_b["league"], "player_b": player_b["player"],
        "player_a_indicator": player_a.get("indicator", "NONE"),
        "player_b_indicator": player_b.get("indicator", "NONE"),
        "max_gap_minutes": max_gap_minutes, "operational_window_hours": DEFAULT_OPERATIONAL_WINDOW_HOURS,
        "matches": rows,
    }


def match_coincident_pair(player_a, matches_a, player_b, matches_b, *, max_gap_minutes=DEFAULT_MAX_COINCIDENT_GAP_MINUTES):
    max_gap_minutes = _validate_gap(max_gap_minutes)
    history_a = player_match_history(matches_a, player_a)
    history_b = player_match_history(matches_b, player_b)
    return _match_histories(player_a, history_a, player_b, history_b, max_gap_minutes)


def calculate_all_coincident_pairs(records, selected_players=None, *, max_gap_minutes=DEFAULT_MAX_COINCIDENT_GAP_MINUTES, snapshot=None, reference_time=None, window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS):
    max_gap_minutes = _validate_gap(max_gap_minutes)
    materialized = list(records)
    eligible_count = 0
    if snapshot is not None:
        eligible_players = _eligible_automatic_player_refs(snapshot)
        eligible_count = len(eligible_players)
        selected_players = eligible_players[:MAX_AUTOMATIC_CANDIDATES]
    selected_players = selected_players or []
    selected_count = len(selected_players)
    pairs = generate_selected_pairs(selected_players)
    if reference_time is not None:
        reference = reference_time if reference_time.tzinfo else reference_time.replace(tzinfo=timezone.utc)
        reference = reference.astimezone(timezone.utc)
        from datetime import timedelta
        lower = reference - timedelta(hours=window_hours)
        materialized = [row for row in materialized if _timestamp(row) is not None and lower <= _timestamp(row) <= reference]
    histories = {}
    for player in {(_ref_key(p)): p for pair in pairs for p in pair}.values():
        histories[_ref_key(player)] = player_match_history(materialized, player)
    analyses = [
        _match_histories(a, histories[_ref_key(a)], b, histories[_ref_key(b)], max_gap_minutes)
        for a, b in pairs
    ]
    return CoincidentPairResults(
        analyses, eligible_players=eligible_count,
        selected_candidates=selected_count,
    )


def load_all_coincident_pairs(tracked_players_path: str | Path, gt_path=GT_HISTORY_PATH, eadriatic_path=EADRIATIC_HISTORY_PATH, *, max_gap_minutes=DEFAULT_MAX_COINCIDENT_GAP_MINUTES):
    tracked = load_tracked_players(tracked_players_path)
    records = load_all_history(gt_path, eadriatic_path)
    reference = datetime.now(timezone.utc)
    snapshot = calculate_operational_snapshot(records, tracked, reference_time=reference)
    return calculate_all_coincident_pairs(records, snapshot=snapshot, reference_time=reference, max_gap_minutes=max_gap_minutes)
