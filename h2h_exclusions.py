"""Persistent directional exclusions scoped to a tracked group."""
import json
import math
from pathlib import Path
from match_history import name_key
from selected_players import load_tracked_players

PREFIX = "@H2H_EXCLUDE||"
MIN_GAP_PREFIX = "@H2H_MIN_GAP||"


def load_h2h_min_gap(path):
    cutoff = -10.0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(MIN_GAP_PREFIX):
            cutoff = float(line.strip()[len(MIN_GAP_PREFIX):])
            if not math.isfinite(cutoff) or not -100 <= cutoff <= 100:
                raise ValueError("H2H_MIN_GAP must be between -100 and 100 points")
    return cutoff


def parse_exclusion(line):
    if not line.strip().startswith(PREFIX):
        return None
    payload = line.strip()[len(PREFIX):].strip()
    if not payload:
        return None
    if not payload.startswith('{'):
        parts = [part.strip() for part in payload.split('|')]
        if len(parts) != 3 or parts[0].upper() not in {'GT', 'EADRIATIC'} or not all(parts):
            raise ValueError('use @H2H_EXCLUDE||LIGA|Jugador A|Jugador B')
        if name_key(parts[1]) == name_key(parts[2]):
            raise ValueError('H2H exclusion requires two different players')
        return dict(league=parts[0].upper(), player=parts[1], rival=parts[2])
    # Read existing JSON exclusions so users do not lose their previous choices.
    value = json.loads(payload)
    if (value.get("league") not in {"GT", "EADRIATIC"} or type(value.get("group")) is not int
            or value["group"] < 1 or not value.get("player") or not value.get("rival")
            or ("members" in value and (not isinstance(value["members"], list) or not value["members"]))):
        raise ValueError("invalid H2H exclusion")
    return value


def group_metadata(path):
    groups = {}
    for row in load_tracked_players(path):
        key = (row["league"], row["group_index"] + 1)
        groups.setdefault(key, []).append(row["player"])
    return groups


def load_h2h_exclusions(path):
    groups = group_metadata(path)
    excluded = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        entry = parse_exclusion(line)
        if entry is None:
            continue
        player, rival = name_key(entry["player"]), name_key(entry["rival"])
        for (league, index), members in groups.items():
            if league != entry['league'] or ('group' in entry and index != entry['group']):
                continue
            keys = {name_key(p) for p in members if p}
            if player == rival or not {player, rival}.issubset(keys):
                continue
            if "members" not in entry or sorted(keys) == sorted(name_key(p) for p in entry["members"] if p):
                excluded.add((league, player, rival))
    return excluded
