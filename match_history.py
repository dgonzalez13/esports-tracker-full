"""Shared validation and atomic JSONL persistence for match perspectives."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import unicodedata
import warnings


SCHEMA_VERSION = 1

REQUIRED_FIELDS = (
    "schema_version", "league", "match_id", "perspective_id", "player",
    "player_key", "rival", "rival_key", "result", "timestamp",
    "timestamp_utc", "timestamp_precision", "timezone",
    "timezone_inferred", "home_away", "home_score", "away_score",
    "source_type", "source_file", "data_quality",
)

OPTIONAL_FIELDS = (
    "native_match_id", "competition", "round", "group_key",
    "group_players", "source_block_order", "source_row_order",
    "collected_at",
)

QUALITY_RANK = {"partial": 0, "inferred": 1, "complete": 2}


class MatchHistoryError(ValueError):
    """Raised when history input is malformed or internally inconsistent."""


def clean_name(value):
    if not isinstance(value, str):
        raise MatchHistoryError("player names must be strings")
    cleaned = unicodedata.normalize("NFKC", value.strip())
    if not cleaned:
        raise MatchHistoryError("player names cannot be empty")
    return cleaned


def name_key(value):
    return clean_name(value).casefold()


def perspective_id(match_id, player):
    return f"{match_id}:{name_key(player)}"


def result_pair(home_score, away_score):
    if home_score > away_score:
        return "V", "D"
    if home_score < away_score:
        return "D", "V"
    return "E", "E"


def validate_perspective_pair(records):
    if len(records) != 2:
        raise MatchHistoryError("a finalized match must have two perspectives")
    home = next((row for row in records if row.get("home_away") == "home"), None)
    away = next((row for row in records if row.get("home_away") == "away"), None)
    if home is None or away is None:
        raise MatchHistoryError("perspective pair must contain one home and one away record")
    shared = (
        "schema_version", "league", "match_id", "native_match_id",
        "timestamp", "timestamp_utc", "timestamp_precision", "timezone",
        "timezone_inferred", "home_score", "away_score", "source_type",
        "source_file", "data_quality", "competition", "round", "group_key",
        "group_players", "source_block_order", "source_row_order", "collected_at",
    )
    for field in shared:
        if field in home or field in away:
            if home.get(field) == away.get(field):
                continue
            raise MatchHistoryError(f"perspective pair disagrees on {field}")
    expected_home, expected_away = result_pair(home["home_score"], home["away_score"])
    if (home.get("result"), away.get("result")) != (expected_home, expected_away):
        raise MatchHistoryError("perspective results are not symmetric with the score")
    if home.get("player_key") != away.get("rival_key") or away.get("player_key") != home.get("rival_key"):
        raise MatchHistoryError("perspective players and rivals are not symmetric")


def _parse_aware_timestamp(value, field, require_z=False):
    if not isinstance(value, str) or not value:
        raise MatchHistoryError(f"{field} must be a non-empty ISO 8601 string")
    if require_z and not value.endswith("Z"):
        raise MatchHistoryError(f"{field} must end in Z")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise MatchHistoryError(f"{field} is not valid ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MatchHistoryError(f"{field} must include a timezone offset")
    return parsed


def validate_record(record):
    if not isinstance(record, dict):
        raise MatchHistoryError("history record must be a JSON object")
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise MatchHistoryError(f"missing required fields: {', '.join(missing)}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise MatchHistoryError(f"schema_version must be {SCHEMA_VERSION}")
    if record["league"] not in {"GT", "EADRIATIC"}:
        raise MatchHistoryError("league must be GT or EADRIATIC")
    if record["result"] not in {"V", "E", "D"}:
        raise MatchHistoryError("result must be V, E or D")
    if record["home_away"] not in {"home", "away"}:
        raise MatchHistoryError("home_away must be home or away")
    if record["timestamp_precision"] not in {"second", "minute"}:
        raise MatchHistoryError("timestamp_precision must be second or minute")
    if record["data_quality"] not in QUALITY_RANK:
        raise MatchHistoryError("data_quality must be complete, partial or inferred")
    if not isinstance(record["timezone_inferred"], bool):
        raise MatchHistoryError("timezone_inferred must be boolean")
    if not isinstance(record["timezone"], str) or not record["timezone"]:
        raise MatchHistoryError("timezone must be a non-empty string")
    for field in ("home_score", "away_score"):
        if isinstance(record[field], bool) or not isinstance(record[field], int) or record[field] < 0:
            raise MatchHistoryError(f"{field} must be a non-negative integer")

    player = clean_name(record["player"])
    rival = clean_name(record["rival"])
    if record["player"] != player or record["rival"] != rival:
        raise MatchHistoryError("player and rival must already be stripped and NFKC-normalized")
    if record["player_key"] != name_key(player) or record["rival_key"] != name_key(rival):
        raise MatchHistoryError("player_key or rival_key is not normalized")
    if record["perspective_id"] != perspective_id(record["match_id"], player):
        raise MatchHistoryError("perspective_id does not match match_id and player_key")
    if not record["match_id"].startswith(record["league"].lower() + ":"):
        raise MatchHistoryError("match_id prefix does not match league")
    for field in ("source_type", "source_file"):
        if not isinstance(record[field], str) or not record[field]:
            raise MatchHistoryError(f"{field} must be a non-empty string")

    timestamp = _parse_aware_timestamp(record["timestamp"], "timestamp")
    timestamp_utc = _parse_aware_timestamp(record["timestamp_utc"], "timestamp_utc", require_z=True)
    if timestamp.astimezone(timestamp_utc.tzinfo) != timestamp_utc:
        raise MatchHistoryError("timestamp and timestamp_utc do not represent the same instant")

    expected_home, expected_away = result_pair(record["home_score"], record["away_score"])
    expected = expected_home if record["home_away"] == "home" else expected_away
    if record["result"] != expected:
        raise MatchHistoryError("result is inconsistent with score and home_away")
    return record


def load_records(path):
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MatchHistoryError(
                    f"invalid JSON in {path} at line {line_number}: {exc.msg}"
                ) from exc
            try:
                validate_record(record)
            except MatchHistoryError as exc:
                raise MatchHistoryError(f"invalid record in {path} at line {line_number}: {exc}") from exc
            records.append(record)
    return records


def _is_missing(value):
    return value is None or value == "" or value == []


def merge_record(existing, candidate):
    """Merge compatible additional fields, retaining old values on conflicts."""
    validate_record(existing)
    validate_record(candidate)
    if existing["perspective_id"] != candidate["perspective_id"]:
        raise MatchHistoryError("cannot merge different perspective IDs")

    merged = dict(existing)
    provenance_fields = {"source_file", "collected_at"}
    for field, new_value in candidate.items():
        old_value = merged.get(field)
        if field not in merged or _is_missing(old_value):
            if not _is_missing(new_value):
                merged[field] = new_value
            continue
        if _is_missing(new_value) or old_value == new_value:
            continue
        if field == "data_quality":
            if QUALITY_RANK[new_value] > QUALITY_RANK[old_value]:
                merged[field] = new_value
            continue
        if field in provenance_fields:
            continue
        warnings.warn(
            f"conflict for {existing['perspective_id']} in field {field}: "
            f"keeping {old_value!r}, received {new_value!r}",
            RuntimeWarning,
            stacklevel=2,
        )
    validate_record(merged)
    return merged


def merge_records(existing_records, candidates):
    indexed = {}
    for record in [*existing_records, *candidates]:
        validate_record(record)
        key = record["perspective_id"]
        indexed[key] = merge_record(indexed[key], record) if key in indexed else dict(record)
    return sorted(
        indexed.values(),
        key=lambda row: (
            row["timestamp_utc"], row["league"], row["match_id"], row["player_key"]
        ),
    )


def write_records_atomic(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = merge_records([], records)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
        ) as handle:
            temp_path = Path(handle.name)
            for record in ordered:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise


def update_history(path, candidates):
    existing = load_records(path)
    merged = merge_records(existing, list(candidates))
    write_records_atomic(path, merged)
    return merged
