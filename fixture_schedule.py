"""Refresh the published calendars separately from finalized match history."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from eadriatic_leagues import fetch_eadriatic_html, parse_history_records
from gtleagues_api import BASE_URL, HEADERS, build_history_records, format_date, parse_gt_timestamp
from match_history import clean_name, name_key

SCHEDULE_PATH = Path(__file__).resolve().parent / "fixture_schedule.json"


def parse_gt_fixtures(matches):
    records = []
    for match in matches:
        # Only status 3 is a confirmed normal final result. Other statuses must
        # not turn a provisional score into a win/loss.
        if match.get("status") == 3:
            final = build_history_records([match], "gt_calendar")
            if final:
                records.extend({**row, "fixture_status": "finished"} for row in final)
                continue
        try:
            stamp = parse_gt_timestamp(match["kickoff"])[1]
            native_id = str(match["id"])
            players = [clean_name(next(p for p in match["participants"] if p["side"] == side)
                                  ["participant"]["player"]["nickname"]) for side in ("home", "away")]
            if not all(players) or match["id"] is None:
                continue
        except (KeyError, TypeError, ValueError, StopIteration):
            continue
        for player, rival in (players, players[::-1]):
            records.append({
                "league": "GT", "match_id": f"gt:{native_id}",
                "player": player, "player_key": name_key(player),
                "rival": rival, "rival_key": name_key(rival),
                "timestamp_utc": stamp, "result": None,
                "fixture_status": "scheduled" if match.get("status") == 0 else "unknown",
            })
    return records


def fetch_gt_fixtures(reference):
    matches = []
    for offset in range(0, 100000, 100):
        response = requests.get(BASE_URL, headers=HEADERS, timeout=30, params={
            "kickoff": f"gte:{format_date(reference - timedelta(hours=8))}",
            "limit": 100, "offset": offset, "sort": "kickoff,matchNr", "xtc": "true",
        })
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError("Invalid GT calendar response")
        matches.extend(page)
        if len(page) < 100:
            return parse_gt_fixtures(matches)
    raise ValueError("GT calendar pagination did not finish")


def load_schedule(path=SCHEDULE_PATH):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sources": {}}


def refresh_schedule(path=SCHEDULE_PATH, reference=None):
    reference = reference or datetime.now(timezone.utc)
    stamp = reference.isoformat()
    previous = load_schedule(path).get("sources", {})
    sources = {}
    collectors = {
        "GT": lambda: fetch_gt_fixtures(reference),
        "EADRIATIC": lambda: parse_history_records(
            fetch_eadriatic_html(), "eadriatic_calendar", stamp, include_scheduled=True),
    }
    for league, collect in collectors.items():
        try:
            fields = ("league", "match_id", "player", "player_key", "rival", "rival_key",
                      "timestamp_utc", "result", "fixture_status")
            sources[league] = {"updated_at": stamp, "records": [
                {key: row.get(key) for key in fields} for row in collect()]}
            print(f'{league}: {len(sources[league]["records"])} calendar perspectives')
        except (requests.RequestException, ValueError) as error:
            sources[league] = {**previous.get(league, {"records": []}), "error": str(error) or type(error).__name__}
            print(f"{league}: calendar refresh failed; previous snapshot retained")
    payload = {"sources": sources}
    target = Path(path)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return payload


if __name__ == "__main__":
    refresh_schedule()
