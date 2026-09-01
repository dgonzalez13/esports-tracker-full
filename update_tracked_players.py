"""Refresh the four tracked-player groups from their public fixture feeds."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from eadriatic_leagues import extract_player, fetch_eadriatic_html
from gtleagues_api import BASE_URL as GT_FIXTURES_URL, HEADERS as GT_HEADERS
from match_history import clean_name, name_key
from selected_players import load_tracked_players


BASE = Path(__file__).resolve().parent
TRACKED_PLAYERS_FILE = BASE / "tracked_players.txt"
MADRID = ZoneInfo("Europe/Madrid")
GROUP_SIZE = 5
VALID_MODES = {"C", "N"}


@dataclass(frozen=True)
class FixtureGroup:
    start_local: datetime
    players: tuple[str, ...]
    source_id: str


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MADRID)


def parse_gt_fixture_groups(fixtures: Iterable[dict]) -> list[FixtureGroup]:
    seasons: dict[str, dict] = {}
    for fixture in fixtures:
        kickoff = _parse_iso(fixture.get("kickoff"))
        season_id = str(fixture.get("seasonId") or "").strip()
        if kickoff is None or not season_id:
            continue
        bucket = seasons.setdefault(season_id, {"start": kickoff, "players": {}})
        bucket["start"] = min(bucket["start"], kickoff)
        for participant in fixture.get("participants") or []:
            try:
                nickname = clean_name(participant["participant"]["player"]["nickname"])
            except (KeyError, TypeError, ValueError):
                continue
            if nickname:
                bucket["players"].setdefault(name_key(nickname), nickname)
    groups = []
    for season_id, bucket in seasons.items():
        players = tuple(bucket["players"].values())
        if len(players) == GROUP_SIZE:
            groups.append(FixtureGroup(bucket["start"], players, f"gt-season:{season_id}"))
    return sorted(groups, key=lambda group: group.start_local)


def _heading_date(label: str, reference: datetime):
    import re
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", label)
    if match:
        day, month, year = map(int, match.groups())
        return datetime(year, month, day).date()
    return reference.astimezone(MADRID).date()


def parse_eadriatic_fixture_groups(html: str, reference: datetime) -> list[FixtureGroup]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    current = None
    current_time = None
    for element in soup.find_all(["span", "tr"]):
        classes = element.get("class", [])
        if element.name == "span" and "fg-heading" in classes:
            label = element.get_text(" ", strip=True)
            current = {"label": label, "date": _heading_date(label, reference), "times": [], "players": {}}
            blocks.append(current)
            current_time = None
        elif element.name == "span" and "time-heading" in classes and current is not None:
            import re
            raw = element.get_text(strip=True)
            if re.fullmatch(r"\d{2}:\d{2}", raw):
                current_time = datetime.strptime(raw, "%H:%M").time()
                current["times"].append(current_time)
        elif element.name == "tr" and element.get("data-match-href") and current is not None:
            cols = element.find_all("td")
            if len(cols) < 3:
                continue
            for col in (cols[0], cols[2]):
                player = extract_player(col.get_text(" ", strip=True))
                if player:
                    player = clean_name(player)
                    current["players"].setdefault(name_key(player), player)
    groups = []
    for block in blocks:
        players = tuple(block["players"].values())
        if len(players) != GROUP_SIZE or not block["times"]:
            continue
        first_time = min(block["times"])
        start = datetime.combine(block["date"], first_time, MADRID)
        groups.append(FixtureGroup(start, players, f'eadriatic:{block["label"]}'))
    return sorted(groups, key=lambda group: group.start_local)


def select_stream_group(groups: Iterable[FixtureGroup], group_index: int, mode: str, reference: datetime) -> FixtureGroup:
    """Pick the current/next group for one of two interleaved fixture streams.

    Both leagues run two independent five-player rounds back to back rather than on a
    fixed daily clock, so streams are told apart by their position in chronological
    order (they alternate 1, 2, 1, 2, ...) instead of an assumed hour-of-day grid.
    """
    mode = mode.upper()
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be C or N, received {mode!r}")
    if group_index not in (1, 2):
        raise ValueError(f"group_index must be 1 or 2, received {group_index!r}")
    ordered = sorted(groups, key=lambda group: group.start_local)
    stream = ordered[(group_index - 1) % 2 :: 2]
    if mode == "C":
        eligible = [group for group in stream if group.start_local <= reference]
        chosen = eligible[-1] if eligible else None
    else:
        eligible = [group for group in stream if group.start_local > reference]
        chosen = eligible[0] if eligible else None
    if chosen is None:
        available = ", ".join(group.start_local.isoformat() for group in stream[:8]) or "none"
        label = "current" if mode == "C" else "next"
        raise RuntimeError(
            f"no {label} five-player group found for stream {group_index} near "
            f"{reference.astimezone(MADRID).isoformat()}; available: {available}"
        )
    return chosen


def fetch_gt_groups(targets: Iterable[datetime], get: Callable = requests.get) -> list[FixtureGroup]:
    targets = list(targets)
    start = min(targets) - timedelta(minutes=30)
    end = max(targets) + timedelta(hours=2)
    params = {
        "kickoff": f'between:{start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")},'
        f'{end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}',
        "limit": 50, "offset": 0, "sort": "kickoff,matchNr", "xtc": "true",
    }
    fixtures = []
    while True:
        response = get(GT_FIXTURES_URL, params=params, headers=GT_HEADERS, timeout=30)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise RuntimeError("GT fixtures API returned a non-list response")
        fixtures.extend(page)
        if len(page) < params["limit"]:
            break
        params["offset"] += params["limit"]
    return parse_gt_fixture_groups(fixtures)


def fetch_eadriatic_groups(reference: datetime) -> list[FixtureGroup]:
    return parse_eadriatic_fixture_groups(fetch_eadriatic_html(), reference)


def rewrite_tracked_players(path: Path, replacements: dict[tuple[str, int], tuple[str, ...]]) -> None:
    original = path.read_text(encoding="utf-8")
    entries = load_tracked_players(path)
    excluded = {(row["league"], row["player_key"]) for row in entries if not row.get("bettable", True)}
    existing: dict[tuple[str, int], list[str]] = {}
    trailing = []
    positions = {"EADRIATIC": 0, "GT": 0}
    for line in original.splitlines():
        stripped = line.strip()
        if stripped.startswith("@") or not stripped:
            trailing.append(line)
            continue
        if "|" not in stripped:
            trailing.append(line)
            continue
        league = stripped.split("|", 1)[0].strip().upper()
        if league not in positions:
            trailing.append(line)
            continue
        group_index = positions[league] // GROUP_SIZE + 1
        existing.setdefault((league, group_index), []).append(stripped.split("|", 1)[1].rstrip("*").strip())
        positions[league] += 1
    output = []
    for league in ("EADRIATIC", "GT"):
        for group_index in (1, 2):
            players = replacements.get((league, group_index), tuple(existing.get((league, group_index), [])))
            if len(players) != GROUP_SIZE or len({name_key(player) for player in players}) != GROUP_SIZE:
                raise RuntimeError(f"{league} group {group_index} must contain five distinct players")
            for player in players:
                marker = "*" if (league, name_key(player)) in excluded else ""
                output.append(f"{league}|{player}{marker}")
    directives = [line for line in trailing if line.strip().startswith("@")]
    path.write_text("\n".join(output) + "\n\n" + "\n".join(directives) + "\n", encoding="utf-8")


def update_groups(modes: dict[tuple[str, int], str], path=TRACKED_PLAYERS_FILE, reference=None) -> dict:
    reference = reference or datetime.now(timezone.utc)
    gt_groups = (
        fetch_gt_groups([reference - timedelta(hours=12), reference + timedelta(hours=48)])
        if any(league == "GT" for league, _ in modes)
        else []
    )
    eadriatic_groups = fetch_eadriatic_groups(reference) if any(league == "EADRIATIC" for league, _ in modes) else []
    replacements = {}
    selected = {}
    for (league, index), mode in modes.items():
        source = gt_groups if league == "GT" else eadriatic_groups
        group = select_stream_group(source, index, mode, reference)
        replacements[(league, index)] = group.players
        selected[(league, index)] = group
    rewrite_tracked_players(Path(path), replacements)
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser()
    for league in ("eadriatic", "gt"):
        for index in (1, 2):
            parser.add_argument(f"--{league}-group-{index}", required=True, choices=("C", "N"))
    parser.add_argument("--file", type=Path, default=TRACKED_PLAYERS_FILE)
    args = parser.parse_args(argv)
    modes = {
        ("EADRIATIC", 1): args.eadriatic_group_1,
        ("EADRIATIC", 2): args.eadriatic_group_2,
        ("GT", 1): args.gt_group_1,
        ("GT", 2): args.gt_group_2,
    }
    selected = update_groups(modes, path=args.file)
    for (league, index), group in selected.items():
        print(f'{league} group {index}: {", ".join(group.players)} ({group.source_id})')


if __name__ == "__main__":
    main()
