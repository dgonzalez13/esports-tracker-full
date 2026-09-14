"""Calendar pairing uses the same chronological rule as historical pairing."""

from datetime import timedelta

from coincident_matches import _event_sort, _match_histories, _physical_match_key, _timestamp
from match_history import name_key
from selected_players import is_operational_record


def coincidence_state(row, pair):
    results = [row.get(f"player_{side}_result") for side in ("a", "b")]
    expected = [{"GREEN": "V", "RED": "D"}.get(pair.get(f"player_{side}_indicator"))
                for side in ("a", "b")]
    if any(want is not None and result in {"V", "E", "D"} and result != want
           for result, want in zip(results, expected)):
        return "Failed"
    if all(result in {"V", "E", "D"} for result in results):
        return "Hit" if all(expected) else "No signal"
    if any(result in {"V", "E", "D"} for result in results):
        return "Waiting for B" if results[0] in {"V", "E", "D"} else "Waiting for A"
    return "Pending"


def attach_schedules(pairs, records, schedule, reference, excluded_keys=None):
    """Attach calendars without counting unresolved or unpaired games as misses."""
    sources = schedule.get("sources", {})
    lower = reference - timedelta(hours=8)
    merged = {}
    for row in records:
        if _timestamp(row) is not None and lower <= _timestamp(row) <= reference:
            merged[(_physical_match_key(row), row.get("player_key"))] = dict(row)
    for source in sources.values():
        for row in source.get("records", []):
            if _timestamp(row) is not None and _timestamp(row) >= lower:
                merged[(_physical_match_key(row), row.get("player_key"))] = dict(row)
    available = [r for r in merged.values() if is_operational_record(r, excluded_keys)]
    for pair in list(pairs) + list(getattr(pairs, "custom_pairs", [])):
        pair["calendar_reference"] = reference
        players = [{"league": pair[f"player_{side}_league"], "player": pair[f"player_{side}"],
                    "player_key": name_key(pair[f"player_{side}"]),
                    "indicator": pair.get(f"player_{side}_indicator", "NONE")}
                   for side in ("a", "b")]
        pair["calendar_sources"] = {p["league"]: sources.get(p["league"], {}) for p in players}
        if not any(p["league"] in sources for p in players):
            pair["calendar_matches"] = []
            pair["unpaired_matches"] = []
            continue
        histories = [sorted((r for r in available if r["league"] == p["league"]
                             and r["player_key"] == p["player_key"]), key=_event_sort) for p in players]
        statuses = {(r["league"], r["match_id"]): r.get("fixture_status") for h in histories for r in h}
        analysis = _match_histories(players[0], histories[0], players[1], histories[1], pair["max_gap_minutes"])
        paired_ids = set()
        calendar, completed, settled = [], [], []
        for row in analysis["matches"]:
            row["state"] = coincidence_state(row, pair)
            for side in ("a", "b"):
                paired_ids.add((row[f"player_{side}_league"], row[f"player_{side}_match_id"]))
                row[f"player_{side}_fixture_status"] = statuses.get(
                    (row[f"player_{side}_league"], row[f"player_{side}_match_id"]))
            finished = all(row.get(f"player_{side}_result") in {"V", "E", "D"} for side in ("a", "b"))
            if finished:
                completed.append(row)
            else:
                calendar.append(row)
            if finished or row["state"] == "Failed":
                settled.append(row)
        pair["matches"] = completed
        pair["metric_matches"] = settled
        pair["calendar_matches"] = calendar
        pair["unpaired_matches"] = sorted(
            (dict(r, side=side.upper()) for side, history in zip(("a", "b"), histories) for r in history
             if (r["league"], r["match_id"]) not in paired_ids), key=_event_sort)


def fixture_label(result, timestamp, reference, status=None):
    if result in {"V", "E", "D"}:
        return f"Finished ({result})"
    if status == "unknown":
        return "Status unconfirmed"
    from datetime import datetime
    kickoff = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return "Scheduled" if kickoff > reference else "Awaiting confirmed result"
