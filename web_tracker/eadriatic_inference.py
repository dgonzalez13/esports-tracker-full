"""Possible pending encounters inferred from recent saved results, never fixtures."""
from datetime import datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from match_history import name_key

from current_streaks_v2 import _record_time
from eadriatic_saved_results import SOURCE_TYPE
from web_tracker.pair_series_schedule import pair_series_schedule


STARTS_PATH = Path(__file__).resolve().parent.parent / 'eadriatic' / 'estimated_starts.json'
OFFSETS = (0, 75, 165, 240, 315, 390)
MADRID = ZoneInfo('Europe/Madrid')


def parse_start_inputs(value):
    entries = []
    for line in value.replace(';', '\n').splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split('|')]
        if len(parts) != 3 or not all(parts):
            raise ValueError('Use Player|Rival|YYYY-MM-DD HH:MM, separated by semicolons')
        a, b, raw = parts
        if name_key(a) == name_key(b):
            raise ValueError('An estimated series needs two different players')
        stamp = datetime.strptime(raw, '%Y-%m-%d %H:%M').replace(tzinfo=MADRID)
        entries.append(dict(player=a, rival=b, start=stamp.isoformat()))
    return entries


def load_starts(path=STARTS_PATH):
    path = Path(path)
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(entries, list):
        raise ValueError('Estimated starts must be a JSON list')
    for row in entries:
        if not all(isinstance(row.get(k), str) and row[k] for k in ('player', 'rival', 'start')):
            raise ValueError('Invalid estimated start entry')
        if datetime.fromisoformat(row['start']).tzinfo is None:
            raise ValueError('Estimated start must include timezone')
    return entries


def save_starts(entries, path=STARTS_PATH, *, apply=False):
    current = load_starts(path)
    def identity(row):
        return (*sorted((name_key(row['player']), name_key(row['rival']))),
                datetime.fromisoformat(row['start']).astimezone(MADRID).date())
    merged = {identity(row): row for row in current}
    merged.update({identity(row): row for row in entries})
    updated = list(merged.values())
    changed = updated != current
    if apply and changed:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
    return changed


def estimate_pair_schedule(stamps, reference, pair, starts):
    stamps = sorted(set(stamps))
    first = stamps[0]
    anchors = {first - timedelta(minutes=offset) for offset in OFFSETS}
    anchors = {anchor for anchor in anchors
               if all(stamp in {anchor + timedelta(minutes=o) for o in OFFSETS} for stamp in stamps)}
    matching = [datetime.fromisoformat(row['start']) for row in starts
                if tuple(sorted((name_key(row['player']), name_key(row['rival'])))) == pair
                and datetime.fromisoformat(row['start']) <= first <= datetime.fromisoformat(row['start']) + timedelta(minutes=OFFSETS[-1])]
    manual = bool(matching)
    if manual:
        anchors = set(matching) & anchors
    if len(anchors) != 1:
        return dict(estimated_fixtures=[], estimate_status='Indicar primera hora o importar mas resultados')
    anchor = next(iter(anchors))
    slots = [anchor + timedelta(minutes=o) for o in OFFSETS]
    if stamps != slots[:len(stamps)]:
        return dict(estimated_fixtures=[], estimate_status='Faltan resultados anteriores: completar importacion')
    return dict(first_estimated=anchor.isoformat(),
                estimate_status='Estimado: inicio manual' if manual else 'Estimado: pauta observada',
                estimated_fixtures=[dict(timestamp=stamp.isoformat(), started=stamp <= reference,
                                         estimated=True, match_number=i+1)
                                    for i, stamp in enumerate(slots) if stamp not in stamps])


def infer_eadriatic_pairs(records, reference, published_fixtures, starts=()):
    recent = [row for row in records if row.get('league') == 'EADRIATIC'
              and row.get('result') in {'V', 'E', 'D'}
              and _record_time(row) is not None
              and reference - timedelta(hours=8) <= _record_time(row) <= reference]
    sequences, _ = pair_series_schedule(recent, {}, reference)
    manual_pairs, names, latest, times = set(), {}, {}, {}
    for row in recent:
        a, b = row.get('player_key'), row.get('rival_key')
        if not a or not b or a == b:
            continue
        pair = tuple(sorted((a, b)))
        names[a], names[b] = row.get('player', a), row.get('rival', b)
        stamp = _record_time(row)
        times.setdefault(pair, set()).add(stamp)
        latest[pair] = max(stamp, latest.get(pair, stamp))
        if row.get('source_type') == SOURCE_TYPE:
            manual_pairs.add(pair)
    result = []
    for a, b in sorted(manual_pairs):
        sequence = sequences.get(('EADRIATIC', a, b), '')
        played = len(sequence)
        if (not 0 < played < 6
                or published_fixtures.get(('EADRIATIC', (a, b)))):
            continue
        result.append(dict(player=names[a], rival=names[b], player_key=a, rival_key=b,
                           observed=played, possible_remaining=6-played,
                           last_result=latest[(a, b)].isoformat(),
                           **estimate_pair_schedule(times[(a, b)], reference, (a, b), starts)))
    return sorted(result, key=lambda row: row['last_result'], reverse=True)
