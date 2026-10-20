"""Offline BetsAPI/BsportsFan HTML and MHTML import for Eadriatic results."""
from collections import defaultdict
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from match_history import (
    SCHEMA_VERSION, MatchHistoryError, clean_name, name_key, perspective_id,
    result_pair, validate_record, validate_perspective_pair,
)

SOURCE_TYPE = 'betsapi_saved_html'
MADRID = ZoneInfo('Europe/Madrid')
LEAGUE_PATH = re.compile(r'/(?:soccer|football)/le?/33440(?:/|$)')


def read_saved_html(path):
    """Decode a page or the main HTML part, including Chrome view-source saves."""
    path = Path(path)
    raw = path.read_bytes()
    location = None
    if path.suffix.lower() in {'.mhtml', '.mht'}:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        location = message.get('Snapshot-Content-Location')
        parts = [p for p in message.walk() if p.get_content_type() == 'text/html']
        if not parts:
            raise ValueError(f'{path.name}: no HTML part in MHTML')
        part = next((p for p in parts if p.get('Content-Location') == location), parts[0])
        location = part.get('Content-Location') or location
        raw = part.get_payload(decode=True)
    # The sample's MIME part omits charset; its original page declares UTF-8.
    html = raw.decode('utf-8-sig')
    soup = BeautifulSoup(html, 'html.parser')
    source_lines = soup.select('td.line-content')
    if source_lines:
        html = '\n'.join(line.get_text() for line in source_lines)
    return html, location


def parse_saved_results(html, source_file, source_url=None):
    soup = BeautifulSoup(html, 'html.parser')
    canonical = soup.select_one('link[rel=canonical][href]')
    url = canonical['href'] if canonical else source_url
    host = urlparse(url or '').hostname or ''
    if (not any(host == d or host.endswith('.' + d) for d in ('betsapi.com', 'bsportsfan.com'))
            or not LEAGUE_PATH.search(urlparse(url or '').path)):
        raise ValueError('Expected saved results for Eadriatic league 33440 on BetsAPI/BsportsFan')
    records, seen = [], {}
    for row in soup.select('table tbody tr'):
        stamp_node = row.select_one('[data-dt]')
        if stamp_node is None:
            continue
        cells = row.find_all('td', recursive=False)
        if len(cells) < 4:
            raise ValueError('Unexpected result table layout')
        teams = cells[2].select('a[href]')
        score_link = cells[3].select_one('a[href]')
        score = re.fullmatch(r'(\d+)\s*[-:]\s*(\d+)', cells[3].get_text(' ', strip=True))
        if not score:
            # Scheduled, cancelled or postponed rows are not final results.
            continue
        event = re.search(r'/(?:soccer|football)/r/(\d+)(?:/|$)',
                          score_link.get('href', '') if score_link else '')
        if len(teams) != 2 or event is None:
            raise ValueError('Final result without two players or a stable event ID')
        names, team_names = [], []
        for team in teams:
            label = team.get_text(' ', strip=True)
            player = re.search(r'\(([^()]+)\)(?:\s+Esports)?\s*$', label, re.I)
            if player is None:
                raise ValueError(f'Cannot identify player in {label!r}')
            names.append(clean_name(player[1]))
            team_names.append(clean_name(label[:player.start()]))
        if name_key(names[0]) == name_key(names[1]):
            raise ValueError('A player cannot face themselves')
        stamp = datetime.fromisoformat(stamp_node['data-dt'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Result timestamp must include its timezone')
        stamp = stamp.astimezone(timezone.utc)
        home, away = map(int, score.groups())
        match_id = f'eadriatic:betsapi:{event[1]}'
        identity = (stamp.isoformat(), tuple(map(name_key, names)), home, away)
        if match_id in seen:
            if seen[match_id] != identity:
                raise ValueError(f'Conflicting duplicate event {match_id}')
            continue
        seen[match_id] = identity
        outcomes = result_pair(home, away)
        pair = []
        for index, player in enumerate(names):
            pair.append(dict(
                schema_version=SCHEMA_VERSION, league='EADRIATIC', match_id=match_id,
                native_match_id=event[1], perspective_id=perspective_id(match_id, player),
                player=player, player_key=name_key(player), rival=names[1-index],
                rival_key=name_key(names[1-index]), result=outcomes[index],
                home_away='home' if index == 0 else 'away', home_score=home, away_score=away,
                timestamp=stamp.astimezone(MADRID).isoformat(timespec='seconds'),
                timestamp_utc=stamp.isoformat(timespec='seconds').replace('+00:00', 'Z'),
                timestamp_precision='second', timezone='UTC', timezone_inferred=False,
                source_type=SOURCE_TYPE, source_file=source_file, source_url=url,
                data_quality='complete', player_team=team_names[index],
                rival_team=team_names[1-index],
            ))
        validate_perspective_pair(pair)
        records.extend(pair)
    if not records:
        raise ValueError('No finalized results found; check the saved page and result table')
    return sorted(records, key=lambda r: (r['timestamp_utc'], r['match_id'], r['player_key']))


def result_key(row):
    stamp = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00'))
    return row['league'], stamp, row['player_key'], row['rival_key']


def with_alternate_origin(official, provisional):
    row = dict(official)
    aliases = [dict(alias) for alias in row.get('alternate_sources', [])]
    for origin in [provisional, *provisional.get('alternate_sources', [])]:
        alias = {k: origin.get(k) for k in (
            'match_id', 'source_type', 'source_file', 'source_url',
            'timestamp_utc', 'home_score', 'away_score', 'home_away', 'result')}
        if alias not in aliases:
            aliases.append(alias)
    row['alternate_sources'] = aliases
    return row


def reconcile_saved_sources(records):
    """Official data supersedes manual data for the same exact match.

    A manual import only fills missing matches. Ambiguous IDs and nearby but
    different kickoff times require review rather than a guessed association.
    """
    if not any(r.get('source_type') == SOURCE_TYPE for r in records):
        return records
    groups = defaultdict(list)
    by_id = {}
    by_pair = defaultdict(list)
    for row in records:
        validate_record(row)
        key = result_key(row)
        if row['source_type'] == SOURCE_TYPE:
            identity = (key, row['home_away'], row['home_score'], row['away_score'])
            previous = by_id.setdefault(row['perspective_id'], identity)
            if previous != identity:
                raise MatchHistoryError(f'Conflicting saved event {row["match_id"]}')
        groups[key].append(row)
        if row['league'] == 'EADRIATIC':
            by_pair[(row['player_key'], row['rival_key'])].append(row)
    output = []
    for key, rows in groups.items():
        manual = [r for r in rows if r['source_type'] == SOURCE_TYPE]
        official = [r for r in rows if r['source_type'] == 'eadriatic_html']
        if manual and official:
            if len({r['match_id'] for r in manual}) > 1 or len({r['match_id'] for r in official}) > 1:
                raise MatchHistoryError(f'Ambiguous cross-source match for {key}')
            chosen = [dict(r) for r in official]
            for index, row in enumerate(chosen):
                for provisional in manual:
                    row = with_alternate_origin(row, provisional)
                chosen[index] = row
            output.extend(chosen)
        else:
            if key[0] == 'EADRIATIC':
                for row in rows:
                    for other in by_pair[(row['player_key'], row['rival_key'])]:
                        if ((row['source_type'] == SOURCE_TYPE) != (other['source_type'] == SOURCE_TYPE)
                                and 0 < abs((key[1] - result_key(other)[1]).total_seconds()) <= 300):
                            raise MatchHistoryError(f'Cross-source kickoff mismatch near {key[1]}; review before importing')
            output.extend(rows)
    return output


def import_saved_results(paths, history_path, apply=False, export_dir=None, complete_days=()):
    from match_history import load_records, merge_records, write_records_atomic
    from eadriatic_leagues import build_df, process, save_txt

    existing = load_records(history_path)
    candidates, pages = [], []
    for filename in paths:
        path = Path(filename)
        html, url = read_saved_html(path)
        parsed = parse_saved_results(html, path.name, url)
        candidates.extend(parsed)
        pages.append({'file': path.name, 'matches': len(parsed) // 2, 'url': url})
        if export_dir:
            target = Path(export_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / (path.name + '.html')).write_text(html, encoding='utf-8')
    merged = merge_records(existing, candidates)
    old_keys = {result_key(r) for r in existing}
    added = [r for r in merged if result_key(r) not in old_keys]
    dates = sorted({r['timestamp'][:10] for r in candidates})
    complete_days = set(complete_days)
    for date in complete_days:
        if datetime.strptime(date, '%Y-%m-%d').date().isoformat() != date or date not in dates:
            raise ValueError(f'Complete day must be YYYY-MM-DD and covered by the input: {date}')
    stamps = [datetime.fromisoformat(r['timestamp']) for r in candidates]
    summary = dict(applied=apply, pages=pages, input_matches=len({r['match_id'] for r in candidates}),
                   added_matches=len({r['match_id'] for r in added}),
                   first_madrid=min(stamps).isoformat(), last_madrid=max(stamps).isoformat(),
                   affected_dates=dates, coverage='partial; only supplied pages, no completeness assumed')
    summary['daily_stats_rebuilt'] = sorted(complete_days) if apply else []
    summary['daily_stats_pending_complete_export'] = sorted(set(dates) - complete_days)
    if export_dir:
        target = Path(export_dir)
        (target / 'normalized_results.jsonl').write_text(
            ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in candidates), encoding='utf-8')
        (target / 'import_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    if apply:
        history_path = Path(history_path)
        if history_path.exists():
            backup = history_path.with_name(history_path.name + '.before_manual_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            shutil.copy2(history_path, backup)
        write_records_atomic(history_path, merged)
        for date in sorted(complete_days):
            # Use all available results of this real local date, never today's stale page.
            day = [r for r in merged if r['league'] == 'EADRIATIC' and r['home_away'] == 'home'
                   and datetime.fromisoformat(r['timestamp_utc'].replace('Z', '+00:00')).astimezone(MADRID).date().isoformat() == date]
            day.sort(key=lambda r: (r['timestamp_utc'], r['match_id']))
            matches = [(r['player'], r['home_score'], r['away_score'], r['rival']) for r in day]
            df, vs = build_df(process(matches))
            daily_path = history_path.parent / (date.replace('-', '') + '_eadriatic_player_stats.txt')
            if daily_path.exists():
                shutil.copy2(daily_path, daily_path.with_name(daily_path.name + '.before_manual_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
            save_txt(df, vs, target_date=datetime.fromisoformat(date), output_dir=history_path.parent)
    return summary
