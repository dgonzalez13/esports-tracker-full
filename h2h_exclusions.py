"""Persistent directional exclusions scoped to a tracked group."""
import json
from pathlib import Path
from match_history import name_key
from selected_players import load_tracked_players

PREFIX = "@H2H_EXCLUDE||"


def parse_exclusion(line):
    if not line.strip().startswith(PREFIX):
        return None
    value = json.loads(line.strip()[len(PREFIX):])
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
        members = groups.get((entry["league"], entry["group"]), [])
        keys = {name_key(p) for p in members if p}
        player, rival = name_key(entry["player"]), name_key(entry["rival"])
        if player == rival or not {player, rival}.issubset(keys):
            continue
        if "members" not in entry or sorted(keys) == sorted(name_key(p) for p in entry["members"] if p):
            excluded.add((entry["league"], name_key(entry["player"]), name_key(entry["rival"])))
    return excluded
