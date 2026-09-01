import json
from html import escape
from pathlib import Path
from datetime import datetime, timezone
import sys
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from coincident_matches import (
    MAX_AUTOMATIC_CANDIDATES,
    calculate_all_coincident_pairs,
)
from current_streaks_v2 import (
    DEFAULT_OPERATIONAL_WINDOW_HOURS, build_current_streaks_v2_payload,
    calculate_operational_snapshot,
)
from history_query import load_all_history
from match_history import name_key
from selected_players import (
    bettable_player_keys, excluded_player_keys, is_operational_record,
    load_coincident_config, load_tracked_players,
)
DOCS_DIR = BASE / "docs"
GROUP_ANALYSIS_FILE = BASE / "group_analysis.json"
TRACKED_PLAYERS_FILE = BASE / "tracked_players.txt"

LEAGUES = {
    "GT": {
        "title": "GT League",
        "data_dir": BASE / "gt" / "data",
    },
    "EADRIATIC": {
        "title": "Eadriatic League",
        "data_dir": BASE / "eadriatic" / "data",
    },
}


def load_group_analysis():
    with open(GROUP_ANALYSIS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def latest_stats_file(folder):
    files = list(folder.glob("*player_stats.txt"))

    if not files:
        return None

    return max(files, key=lambda p: p.name[:8])


def load_daily_stats(txt_file):
    if txt_file is None:
        return []

    rows = []

    with open(txt_file, "r", encoding="utf-8") as f:
        in_table = False

        for line in f:
            if line.startswith("player"):
                in_table = True
                continue

            if not in_table:
                continue

            if not line.strip():
                break

            parts = line.split()

            if len(parts) < 7:
                continue

            rows.append({
                "player": parts[0],
                "W": int(parts[1]),
                "D": int(parts[2]),
                "L": int(parts[3]),
                "played": int(parts[4]),
                "stk": int(parts[5]),
                "seq": parts[6],
            })

    return sorted(rows, key=lambda row: row["played"], reverse=True)


def calculate_streaks(seq):
    if not seq:
        return 0, 0

    # Racha sin ganar
    stk_win = 0
    for c in reversed(seq):
        if c == "V":
            break
        stk_win += 1

    # Racha sin perder
    stk_lose = 0
    for c in reversed(seq):
        if c == "D":
            break
        stk_lose += 1

    return stk_win, stk_lose


def _daily_local_bounds(stats_file):
    if stats_file is None:
        return None
    try:
        start = datetime.strptime(stats_file.name[:8], "%Y%m%d").replace(
            tzinfo=ZoneInfo("Europe/Madrid")
        )
    except (ValueError, TypeError):
        return None
    from datetime import timedelta
    return start, start + timedelta(days=1)


def _event_local_time(event):
    raw = event.get("timestamp_utc") or event.get("timestamp")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("Europe/Madrid"))


def load_current_streaks(tracked_players=None, records=None):
    streaks = {}
    if tracked_players is None:
        tracked_players = load_tracked_players(TRACKED_PLAYERS_FILE)
    tracked_keys = bettable_player_keys(tracked_players)
    excluded_keys = excluded_player_keys(tracked_players)

    for league, config in LEAGUES.items():
        stats_file = latest_stats_file(config["data_dir"])
        stats = load_daily_stats(stats_file)

        rows = []

        for row in stats:
            if (league, name_key(row["player"])) in excluded_keys:
                continue
        
            stk_win, stk_lose = calculate_streaks(row["seq"])

            rows.append({
                "player": row["player"],
                "W": row["W"],
                "D": row["D"],
                "L": row["L"],
                "played": row["played"],
                "stk_win": stk_win,
                "stk_lose": stk_lose,
                "seq": row["seq"],
                "tracked": (league, name_key(row["player"])) in tracked_keys,
                "balance":
                    "🟢"
                    if (league, name_key(row["player"])) in tracked_keys
                    and row["W"] >= row["D"] + row["L"]
                    else
                    "🔴"
                    if (league, name_key(row["player"])) in tracked_keys
                    and row["L"] >= row["W"] + row["D"]
                    else
                    "",
            })

        # Rebuild tracked rows only for the local day represented by this TXT.
        # Without a reliable TXT date, preserve the original daily Legacy rows.
        bounds = _daily_local_bounds(stats_file)
        reconstructed = records is not None and bounds is not None
        if reconstructed:
            day_start, day_end = bounds
            operational = {}
            for event in records:
                if not is_operational_record(event, excluded_keys):
                    continue
                local_time = _event_local_time(event)
                if local_time is None or not day_start <= local_time < day_end:
                    continue
                identity = (str(event["league"]).strip().upper(), event["player_key"])
                if identity[0] != league or identity not in tracked_keys:
                    continue
                if event.get("result") not in {"V", "E", "D"}:
                    continue
                operational.setdefault(identity, []).append(event)
            rows = [row for row in rows if (league, name_key(row["player"])) not in tracked_keys]
            names = {
                (row["league"], row["player_key"]): row["player"]
                for row in tracked_players if row.get("tracked") and row.get("bettable", True)
            }
            for identity, events in operational.items():
                events.sort(key=lambda event: (
                    str(event.get("timestamp_utc") or event.get("timestamp") or ""),
                    str(event.get("match_id", "")), str(event.get("perspective_id", "")),
                ))
                seq = "".join(event["result"] for event in events)
                stk_win, stk_lose = calculate_streaks(seq)
                wins, draws, losses = seq.count("V"), seq.count("E"), seq.count("D")
                rows.append({
                    "player": names.get(identity, str(events[-1].get("player", ""))),
                    "W": wins, "D": draws, "L": losses, "played": len(seq),
                    "stk_win": stk_win, "stk_lose": stk_lose, "seq": seq,
                    "tracked": True,
                    "balance": "🟢" if wins >= draws + losses else (
                        "🔴" if losses >= wins + draws else ""
                    ),
                })
            rows.sort(key=lambda row: row["played"], reverse=True)

        streaks[league] = {
            "title": config["title"],
            "source": "match_history.jsonl (tracked daily) + " + stats_file.name
            if reconstructed else (stats_file.name if stats_file else ""),
            "scope_note": (
                "Tracked rows reconstructed for the TXT day in Europe/Madrid."
                if reconstructed else
                "Fallback: daily TXT retained because its date could not be determined."
            ),
            "rows": rows,
        }

    return streaks


def text(value):
    if value is None:
        return ""

    return escape(str(value))


def fmt_pct(value):
    if value in ("", None):
        return "-"

    return f"{float(value):.2f}%"


def fmt_score(value):
    if value in ("", None):
        return "-"

    return f"{float(value):.2f}"


def metric(label, value, hint=None):
    hint_html = f"<span>{text(hint)}</span>" if hint else ""

    return (
        '<div class="metric">'
        f'<strong>{text(value)}</strong>'
        f'<small>{text(label)}</small>'
        f"{hint_html}"
        "</div>"
    )


def render_page(data, current_streaks, coincident_pairs=None, current_streaks_v2=None):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>eSports Group Dashboard</title>
{render_styles()}
</head>
<body>
<header class="page-header">
    <div>
        <p class="eyebrow">eSports Tracker</p>
        <h1>Group Analysis Dashboard</h1>
    </div>
    <div class="header-meta">
        {metadata_badge("Schema", data.get("schema_version", "-"))}
        {metadata_badge("Generated", data.get("generated_at", "-"))}
    </div>
</header>
<main>
    {render_current_streaks_v2(current_streaks_v2 or {})}
    {render_coincident_matches(coincident_pairs or [], current_streaks_v2 or {})}
    {render_group_dashboard(data, current_streaks)}
</main>
</body>
</html>
"""


def render_styles():
    return """<style>
:root {
    color-scheme: light;
    --bg: #f6f7f9;
    --surface: #ffffff;
    --surface-soft: #f0f3f7;
    --ink: #111827;
    --muted: #5b6472;
    --line: #d7dde5;
    --accent: #14746f;
    --accent-soft: #e0f2ef;
    --warn: #9a3412;
    --warn-soft: #fff3e8;
    --good: #166534;
    --good-soft: #e8f7ee;
    --bad: #991b1b;
    --bad-soft: #feecec;
    --shadow: 0 18px 45px rgba(17, 24, 39, 0.08);
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: Inter, Segoe UI, Arial, sans-serif;
    line-height: 1.4;
}

.page-header {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-end;
    padding: 32px clamp(18px, 4vw, 56px) 20px;
}

.eyebrow {
    margin: 0 0 6px;
    color: var(--accent);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}

h1, h2, h3 {
    margin: 0;
    letter-spacing: 0;
}

h1 {
    font-size: clamp(30px, 4vw, 52px);
    line-height: 1.02;
}

h2 {
    font-size: 22px;
}

h3 {
    font-size: 16px;
}

main {
    padding: 0 clamp(18px, 4vw, 56px) 48px;
}

.header-meta,
.badge-row,
.player-list,
.suggestion-grid,
.section-head,
.league-head {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.header-meta {
    justify-content: flex-end;
}

.badge,
.chip {
    display: inline-flex;
    align-items: center;
    min-height: 28px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--surface);
    color: var(--muted);
    padding: 5px 10px;
    font-size: 12px;
    white-space: nowrap;
}

.chip {
    color: var(--ink);
    background: var(--surface-soft);
    font-weight: 700;
}

.dashboard-section {
    margin-top: 24px;
}

.section-head {
    align-items: end;
    justify-content: space-between;
    margin-bottom: 14px;
}

.section-subtitle {
    margin: 4px 0 0;
    color: var(--muted);
    font-size: 13px;
}

.league-block {
    margin-top: 22px;
}

.league-head {
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 18px;
}

.group-card,
.streak-panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface);
    box-shadow: var(--shadow);
}

.group-card {
    overflow: hidden;
}

.card-header {
    padding: 18px;
    border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, #ffffff, #f7f9fb);
}

.card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 12px;
    margin-bottom: 12px;
}

.league-pill {
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
    padding: 16px 18px 4px;
}

.metric {
    min-height: 86px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface-soft);
    padding: 12px;
}

.metric strong {
    display: block;
    font-size: 24px;
    line-height: 1;
}

.metric small,
.metric span {
    display: block;
    margin-top: 6px;
    color: var(--muted);
    font-size: 12px;
}

.card-section {
    padding: 16px 18px;
    border-top: 1px solid var(--line);
}

.suggestion-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
}

.suggestion {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px;
}

.suggestion.back {
    background: var(--good-soft);
    border-color: #b7dfc5;
}

.suggestion.lay {
    background: var(--bad-soft);
    border-color: #efb4b4;
}

.suggestion-label {
    color: var(--muted);
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
}

.suggestion-player {
    margin-top: 4px;
    font-size: 22px;
    font-weight: 850;
}

.table-wrap {
    width: 100%;
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 13px;
}

th,
td {
    border-bottom: 1px solid var(--line);
    padding: 8px 9px;
    text-align: left;
    vertical-align: top;
    white-space: nowrap;
}

th {
    color: var(--muted);
    background: var(--surface-soft);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
}

.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.seq {
    color: var(--muted);
    font-family: Consolas, ui-monospace, monospace;
    white-space: nowrap;
}

.rank-list {
    display: grid;
    gap: 8px;
    margin-top: 10px;
}

.rank-row {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr) auto;
    gap: 10px;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 9px 10px;
    background: var(--surface);
}

.rank-pos {
    color: var(--muted);
    font-size: 12px;
    font-weight: 800;
}

.rank-name {
    min-width: 0;
    overflow-wrap: anywhere;
    font-weight: 750;
}

.rank-score {
    font-variant-numeric: tabular-nums;
    font-weight: 750;
}

.two-col {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 14px;
}

.streak-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 18px;
}

.streak-panel {
    padding: 16px;
    overflow: hidden;
}

.alert-panel {
    margin-bottom: 18px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface);
    box-shadow: var(--shadow);
    padding: 16px;
    overflow: hidden;
}

.low-sample-row {
    background: var(--warn-soft);
}

.signal-badge,
.confidence-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 800;
    white-space: nowrap;
}

.signal-strong {
    background: var(--good-soft);
    color: var(--good);
}

.signal-watch {
    background: var(--warn-soft);
    color: var(--warn);
}

.confidence-high {
    background: var(--good-soft);
    color: var(--good);
}

.confidence-low {
    background: var(--warn-soft);
    color: var(--warn);
}

details {
    margin-top: 12px;
}

summary {
    cursor: pointer;
    color: var(--accent);
    font-weight: 800;
}

@media (max-width: 720px) {
    .page-header {
        display: block;
    }

    .header-meta {
        justify-content: flex-start;
        margin-top: 14px;
    }

    .cards-grid,
    .streak-grid {
        grid-template-columns: 1fr;
    }

    .card-title-row,
    .league-head,
    .section-head {
        align-items: start;
        flex-direction: column;
    }
}
.coincident-both-green { background: #dcfce7; }
.coincident-both-red { background: #fee2e2; }
.coincident-mixed-confirmed { background: #fef3c7; }
.streak-group-shaded { background: #eef4f8; }

.coincident-pair {
    margin-bottom: 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface);
    box-shadow: var(--shadow);
    overflow: hidden;
}

.coincident-pair > summary {
    cursor: pointer;
    list-style: none;
    padding: 13px 15px;
    font-weight: 800;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.coincident-pair > summary::-webkit-details-marker {
    display: none;
}

.coincident-pair > summary::before {
    content: "▶";
    margin-right: 8px;
    color: var(--muted);
    font-size: 11px;
}

.coincident-pair[open] > summary::before {
    content: "▼";
}

.coincident-pair-body {
    padding: 0 15px 15px;
    border-top: 1px solid var(--line);
}
.coincident-cross-group {
    background: #e0f2fe;
    border-color: #38bdf8;
}

</style>"""


def metadata_badge(label, value):
    return f'<span class="badge">{text(label)}: {text(value)}</span>'


def render_session_streak_panel(league, rows):
    table_rows = []
    for row in rows:
        player = f'{row.get("balance", "")} {row.get("player", "")}'.strip()
        streak = (
            f'{row.get("current_streak_result")} × {row.get("current_streak")}'
            if row.get("current_streak_result") and row.get("current_streak")
            else "—"
        )
        table_rows.append([
            player, f'{row.get("wins", 0)} ({row.get("win_pct", 0):.2f}%)',
            row.get("draws", 0), f'{row.get("losses", 0)} ({row.get("loss_pct", 0):.2f}%)',
            row.get("played", 0),
            row.get("last_24", ""), streak,
        ])
    body = render_table(
        ["PLAYER", "W", "D", "L", "PLAYED", "LAST 24", "STREAK"],
        table_rows, numeric_columns={1, 2, 3, 4}, seq_columns={5},
        row_classes=["streak-group-shaded" if int(row.get("group_index", 0)) % 2 == 0 else "" for row in rows],
    )
    return (
        '<article class="streak-panel"><div class="league-head">'
        f'<h3>{text(LEAGUES.get(league, {}).get("title", league))}</h3>'
        f'{metadata_badge("Visible players", len(rows))}</div>{body}'
        '<p class="section-subtitle">Shading identifies players belonging to the same tracked group.</p></article>'
    )


def render_current_streaks_v2(payload):
    leagues = payload.get("leagues", {})
    panels = [
        render_session_streak_panel(league, leagues.get(league, []))
        for league in ("GT", "EADRIATIC")
    ]
    return (
        '<section class="dashboard-section">'
        '<div class="section-head"><div><h2>Current Streaks — Last 8 Hours</h2>'
        '<p class="section-subtitle">All valid normalized matches in the operational window.</p>'
        '</div><div class="badge-row">'
        f'{metadata_badge("Window", f"{payload.get("operational_window_hours", 8)} hours")}'
        f'{metadata_badge("Source", "match_history.jsonl")}'
        f'{metadata_badge("Minimum matches for automatic selection", 5)}'
        f'{metadata_badge("Indicator threshold", "50%")}'
        '</div></div><div class="streak-grid">'
        f'{"".join(panels)}</div></section>'
    )


def _madrid_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "—"
    return parsed.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")



def _coincident_indicator_strength_lookup(current_streaks_v2):
    lookup = {}
    for league, rows in (current_streaks_v2 or {}).get("leagues", {}).items():
        for row in rows:
            player_key = row.get("player_key")
            indicator = row.get("indicator", "NONE")
            if not player_key:
                continue
            if indicator == "GREEN":
                strength = float(row.get("win_pct", 0.0) or 0.0)
            elif indicator == "RED":
                strength = float(row.get("loss_pct", 0.0) or 0.0)
            else:
                strength = 0.0
            lookup[(str(league).upper(), player_key)] = strength
    return lookup


def _coincident_pair_metrics(pair, strength_lookup):
    matches = sorted(pair.get("matches", []), key=lambda row: row.get("pair_order", 0))
    key_a = (
        str(pair.get("player_a_league", "")).upper(),
        name_key(str(pair.get("player_a", ""))),
    )
    key_b = (
        str(pair.get("player_b_league", "")).upper(),
        name_key(str(pair.get("player_b", ""))),
    )
    strength_a = float(strength_lookup.get(key_a, 0.0))
    strength_b = float(strength_lookup.get(key_b, 0.0))
    combined_pct = strength_a * strength_b / 100.0
    misses = 0
    max_misses = 0
    running_misses = 0
    for row in matches:
        if row.get("confirmation") in {"BOTH_GREEN", "BOTH_RED", "MIXED"}:
            running_misses = 0
        else:
            running_misses += 1
            max_misses = max(max_misses, running_misses)
    for row in reversed(matches):
        if row.get("confirmation") in {"BOTH_GREEN", "BOTH_RED", "MIXED"}:
            break
        misses += 1

    return {
        "combined_pct": round(combined_pct, 2),
        "player_a_pct": round(strength_a, 2),
        "player_b_pct": round(strength_b, 2),
        "misses_since_hit": misses,
        "max_misses_without_hit": max_misses,
    }


def render_coincident_pair(pair, reliability=None):
    matches = sorted(pair.get("matches", []), key=lambda row: row.get("pair_order", 0))
    title = (
        f'{pair.get("player_a_league", "")} · {pair.get("player_a", "")} '
        f'[{pair.get("player_a_indicator", "NONE")}] ↔ '
        f'{pair.get("player_b_league", "")} · {pair.get("player_b", "")} '
        f'[{pair.get("player_b_indicator", "NONE")}]'
    )
    maximum = pair.get("max_gap_minutes", 30)

    if not matches:
        body = (
            f'<p class="section-subtitle">'
            f'No coincident matches within {text(maximum)} minutes.'
            f'</p>'
        )
    else:
        rows = [[
            row.get("pair_order", ""),
            row.get("player_a", ""),
            _madrid_time(row.get("player_a_timestamp")),
            row.get("player_a_result", ""),
            row.get("player_a_rival", ""),
            row.get("player_b", ""),
            _madrid_time(row.get("player_b_timestamp")),
            row.get("player_b_result", ""),
            row.get("player_b_rival", ""),
            f'{row.get("gap_minutes", 0)} min',
            {
                "BOTH_GREEN": "BOTH GREEN",
                "BOTH_RED": "BOTH RED",
                "MIXED": "MIXED",
            }.get(row.get("confirmation"), "—"),
        ] for row in matches]

        row_classes = [
            {
                "BOTH_GREEN": "coincident-both-green",
                "BOTH_RED": "coincident-both-red",
                "MIXED": "coincident-mixed-confirmed",
            }.get(row.get("confirmation"), "")
            for row in matches
        ]

        body = render_table(
            [
                "#", "Player A", "Time A", "Result A", "Opponent A",
                "Player B", "Time B", "Result B", "Opponent B",
                "Gap", "Confirmation",
            ],
            rows,
            numeric_columns={0, 9},
            row_classes=row_classes,
        )

    reliability_badge = ""
    if reliability:
        reliability_badge = (
            f'<span class="badge">'
            f'Combined: {reliability["combined_pct"]:.2f}% · '
            f'Without a hit: {reliability["misses_since_hit"]} · '
            f'Max without a hit: {reliability["max_misses_without_hit"]}'
            f'</span>'
        )

    detail_class = "coincident-pair coincident-cross-group" if pair.get("different_groups") else "coincident-pair"
    return (
        f'<details class="{detail_class}">'
        '<summary>'
        f'<span>{text(title)}</span>'
        '<span class="badge-row">'
        f'{metadata_badge("Matches", len(matches))}'
        f'{reliability_badge}'
        '</span>'
        '</summary>'
        '<div class="coincident-pair-body">'
        '<div class="badge-row" style="margin-top: 12px">'
        f'{metadata_badge("Window", f"{pair.get("operational_window_hours", 8)} hours")}'
        f'{metadata_badge("Maximum gap", f"{maximum} min")}'
        '</div>'
        f'{body}'
        '</div>'
        '</details>'
    )


def _coincident_group_metrics(group, strength_lookup):
    strengths = [
        float(strength_lookup.get((str(player.get("league", "")).upper(), player.get("player_key", "")), 0.0))
        for player in group.get("players", [])
    ]
    combined = 0.0
    if strengths:
        combined = 100.0
        for strength in strengths:
            combined *= strength / 100.0
    matches = sorted(group.get("matches", []), key=lambda row: row.get("group_order", 0))
    misses = 0
    max_misses = 0
    running = 0
    valid = {"ALL_GREEN", "ALL_RED", "MIXED"}
    for row in matches:
        if row.get("confirmation") in valid:
            running = 0
        else:
            running += 1
            max_misses = max(max_misses, running)
    for row in reversed(matches):
        if row.get("confirmation") in valid:
            break
        misses += 1
    return {
        "combined_pct": round(combined, 2),
        "misses_since_hit": misses,
        "max_misses_without_hit": max_misses,
    }


def render_coincident_group(group, reliability):
    players = group.get("players", [])
    matches = sorted(group.get("matches", []), key=lambda row: row.get("group_order", 0))
    title = " ↔ ".join(
        f'{player.get("league", "")} · {player.get("player", "")} [{player.get("indicator", "NONE")}]'
        for player in players
    )
    headers = ["#"]
    for index in range(len(players)):
        label = chr(ord("A") + index)
        headers.extend([f"Player {label}", f"Time {label}", f"Result {label}", f"Opponent {label}"])
    headers.extend(["Gap", "Confirmation"])
    rows = []
    row_classes = []
    labels = {"ALL_GREEN": "ALL GREEN", "ALL_RED": "ALL RED", "MIXED": "MIXED"}
    classes = {
        "ALL_GREEN": "coincident-both-green", "ALL_RED": "coincident-both-red",
        "MIXED": "coincident-mixed-confirmed",
    }
    for row in matches:
        values = [row.get("group_order", "")]
        for member in row.get("members", []):
            values.extend([
                member.get("player", ""), _madrid_time(member.get("timestamp")),
                member.get("result", ""), member.get("rival", ""),
            ])
        values.extend([
            f'{row.get("gap_minutes", 0)} min',
            labels.get(row.get("confirmation"), "—"),
        ])
        rows.append(values)
        row_classes.append(classes.get(row.get("confirmation"), ""))
    body = (
        render_table(headers, rows, numeric_columns={0, len(headers) - 2}, row_classes=row_classes)
        if rows else
        f'<p class="section-subtitle">No coincident matches within {text(group.get("max_gap_minutes", 30))} minutes.</p>'
    )
    badge = (
        f'<span class="badge">Combined: {reliability["combined_pct"]:.2f}% · '
        f'Without a hit: {reliability["misses_since_hit"]} · '
        f'Max without a hit: {reliability["max_misses_without_hit"]}</span>'
    )
    detail_class = "coincident-pair coincident-cross-group" if group.get("different_groups") else "coincident-pair"
    return (
        f'<details class="{detail_class}"><summary>'
        f'<span>{text(title)}</span><span class="badge-row">'
        f'{metadata_badge("Matches", len(matches))}{badge}</span></summary>'
        '<div class="coincident-pair-body"><div class="badge-row" style="margin-top: 12px">'
        f'{metadata_badge("Window", f"{group.get("operational_window_hours", 8)} hours")}'
        f'{metadata_badge("Maximum gap", f"{group.get("max_gap_minutes", 30)} min")}'
        f'</div>{body}</div></details>'
    )


def _render_coincident_group_section(groups, size, strength_lookup, minimum=35.0, minimum_matches=8):
    visible = []
    for group in groups:
        if group.get("size") != size:
            continue
        metrics = _coincident_group_metrics(group, strength_lookup)
        if metrics["combined_pct"] > minimum and len(group.get("matches", [])) >= minimum_matches:
            visible.append((group, metrics))
    visible.sort(key=lambda item: -item[1]["combined_pct"])
    noun = "Triples" if size == 3 else "Groups of 4"
    content = (
        "".join(render_coincident_group(group, metrics) for group, metrics in visible)
        if visible else f'<p class="section-subtitle">No {noun.lower()} meet the &gt; 35% and 8-match minimum.</p>'
    )
    return (
        '<section class="dashboard-section"><div class="section-head"><div>'
        f'<h2>Coincident Matches — {noun} — Last 8 Hours</h2>'
        '<p class="section-subtitle">Only groups above 35% combined with at least 8 coincident matches are shown.</p>'
        f'</div><div class="badge-row">{metadata_badge("Group size", size)}'
        f'{metadata_badge("Minimum combined", "> 35%")} '
        f'{metadata_badge("Minimum matches", ">= 8")}</div></div>{content}</section>'
    )


def render_coincident_matches(pairs, current_streaks_v2=None):
    eligible_players = getattr(pairs, "eligible_players", 0)
    selected_candidates = getattr(pairs, "selected_candidates", 0)
    candidate_limit = getattr(pairs, "candidate_limit", MAX_AUTOMATIC_CANDIDATES)
    selection_mode = getattr(pairs, "selection_mode", "automatic")
    excluded_candidates = getattr(pairs, "excluded_candidates", 0)

    strength_lookup = _coincident_indicator_strength_lookup(current_streaks_v2 or {})
    minimum_combined_pct = 35.0
    visible_pairs = []
    for pair in pairs:
        metrics = _coincident_pair_metrics(pair, strength_lookup)
        if metrics["combined_pct"] > minimum_combined_pct:
            visible_pairs.append((pair, metrics))
    visible_pairs.sort(key=lambda item: -item[1]["combined_pct"])

    content = (
        ''.join(
            render_coincident_pair(pair, reliability)
            for pair, reliability in visible_pairs
        )
        if visible_pairs
        else '<p class="section-subtitle">No pairs exceed the 35% combined threshold.</p>'
    )

    pair_section = (
        '<section class="dashboard-section">'
        '<div class="section-head"><div>'
        '<h2>Coincident Matches — Last 8 Hours</h2>'
        '<p class="section-subtitle">'
        'Only pairs with a combined percentage above 35% are shown.'
        '</p>'
        '</div><div class="badge-row">'
        f'{metadata_badge("Eligible players", eligible_players)}'
        f'{metadata_badge("Selected candidates", selected_candidates)}'
        f'{metadata_badge("Selection mode", selection_mode)}'
        f'{metadata_badge("Excluded candidates", excluded_candidates)}'
        f'{metadata_badge("Candidate limit", candidate_limit if selection_mode == "automatic" else "manual")}'
        f'{metadata_badge("Minimum combined", "> 35%")} '
        '</div></div>'
        f'{content}'
        '</section>'
    )
    groups = getattr(pairs, "groups", [])
    return (
        pair_section
        + _render_coincident_group_section(groups, 3, strength_lookup)
        + _render_coincident_group_section(groups, 4, strength_lookup)
    )


def build_current_status_lookup(current_streaks):
    lookup = {}

    for league, payload in current_streaks.items():
        for row in payload.get("rows", []):
            lookup[(league, row["player"].strip().lower())] = row.get("balance", "")

    return lookup


def render_group_dashboard(data, current_streaks):
    leagues = data.get("leagues", {})
    status_lookup = build_current_status_lookup(current_streaks)
    sections = []

    for league, payload in leagues.items():
        sections.append(render_league_groups(league, payload, status_lookup))

    return (
        '<section class="dashboard-section">'
        '<div class="section-head">'
        "<div>"
        "<h2>Group Analysis</h2>"
        '<p class="section-subtitle">All group statistics are read from group_analysis.json.</p>'
        "</div>"
        f'{metadata_badge("Generated", data.get("generated_at", "-"))}'
        "</div>"
        + "".join(sections)
        + "</section>"
    )


def render_league_groups(league, payload, status_lookup):
    cards = [
        render_group_card(league, payload, group)
        for group in payload.get("groups", [])
    ]

    return (
        '<div class="league-block">'
        '<div class="league-head">'
        f"<h2>{text(LEAGUES.get(league, {}).get('title', league))}</h2>"
        '<div class="badge-row">'
        f'{metadata_badge("Files", payload.get("files_count", "-"))}'
        f'{metadata_badge("From", payload.get("data_from", "-"))}'
        f'{metadata_badge("To", payload.get("data_to", "-"))}'
        "</div>"
        "</div>"
        + render_h2h_alerts(league, payload.get("h2h_alerts", []), status_lookup)
        + f'<div class="cards-grid">{"".join(cards)}</div>'
        "</div>"
    )



def player_with_status(league, player, status_lookup):
    player_name = str(player or "")
    status = status_lookup.get((league, player_name.strip().lower()), "")

    if status:
        return f"{status} {player_name}"

    return player_name


def render_h2h_alerts(league, alerts, status_lookup):
    if not alerts:
        return ""

    html = []

    html.append('<div class="alert-panel">')
    html.append("<h3>H2H Betting Alerts</h3>")
    html.append(
        '<p class="section-subtitle">'
        "Matchups above the configured H2H threshold. "
        "Rows with low sample size are highlighted."
        "</p>"
    )

    html.append('<div class="table-wrap"><table>')
    html.append(
        "<thead><tr>"
        "<th>Player</th><th>Rival</th>"
        "<th>W</th><th>D</th><th>L</th><th>Matches</th>"
        "<th>Win %</th><th>Last 20</th><th>Win % L20</th>"
        "<th>Trend</th><th>Signal</th><th>Sample</th>"
        "</tr></thead><tbody>"
    )

    for alert in alerts:
        confidence = alert.get("confidence", "")
        signal = alert.get("signal", "")
        recent_status = alert.get("recent_sample_status")
        is_low_sample = (
            recent_status == "LOW_SAMPLE"
            if recent_status is not None
            else alert.get("low_sample", confidence == "LOW SAMPLE")
        )

        row_class = ' class="low-sample-row"' if is_low_sample else ""

        signal_class = (
            "signal-strong"
            if signal == "STRONG"
            else "signal-watch"
        )

        signal_label = (
            "🟢 STRONG"
            if signal == "STRONG"
            else "🟡 WATCH"
        )

        recent_available = alert.get("recent_available", 0)
        recent_window = alert.get("recent_window", 20)
        has_recent = bool(recent_available)
        recent_sequence = alert.get("recent_sequence", "") if has_recent else "—"
        recent_pct = fmt_pct(alert.get("recent_win_pct")) if has_recent else "—"
        trend = alert.get("recent_trend") if has_recent else None
        delta = alert.get("recent_win_pct_delta", 0.0)
        trend_symbols = {"UP": "↑", "STABLE": "→", "DOWN": "↓"}
        trend_label = (
            f"{trend_symbols[trend]} {float(delta):+.2f}"
            if trend in trend_symbols
            else "—"
        )
        if not has_recent:
            sample_label = "—"
        elif alert.get("recent_window_complete", recent_available >= recent_window):
            sample_label = f"{recent_available}/{recent_window}"
        else:
            sample_label = f"{recent_available}/{recent_window} · LOW"

        html.append(f"<tr{row_class}>")
        html.append(f"<td>{text(player_with_status(league, alert.get('player', ''), status_lookup))}</td>")
        html.append(f"<td>{text(player_with_status(league, alert.get('rival', ''), status_lookup))}</td>")
        html.append(f'<td class="num">{text(alert.get("W", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("D", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("L", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("matches", ""))}</td>')
        html.append(f'<td class="num">{text(fmt_pct(alert.get("win_pct")))}</td>')

        html.append(f'<td class="seq">{text(recent_sequence)}</td>')
        html.append(f'<td class="num">{text(recent_pct)}</td>')
        html.append(f'<td>{text(trend_label)}</td>')

        html.append(
            '<td>'
            f'<span class="signal-badge {signal_class}">'
            f"{text(signal_label)}"
            "</span>"
            "</td>"
        )
        html.append(
            '<td>'
            '<span class="confidence-badge">'
            f"{text(sample_label)}"
            "</span>"
            "</td>"
        )
        html.append("</tr>")

    html.append("</tbody></table></div>")
    html.append("</div>")

    return "".join(html)

def render_group_card(league, league_payload, group):
    return (
        f'<article class="group-card" id="{text(league.lower())}-{text(group.get("group_id", ""))}">'
        + render_group_header(league, league_payload, group)
        + render_group_metrics(group)
        + render_betting(group)
        + '<div class="card-section two-col">'
        + render_power_ranking(group)
        + render_dominance(group)
        + "</div>"
        + '<div class="card-section">'
        + render_h2h_ranking(group)
        + "</div>"
        + '<div class="card-section">'
        + render_totals("Exact Matches 5/5", group.get("totals_5", []))
        + render_totals("Matches >= 4/5", group.get("totals_4", []))
        + "</div>"
        + '<div class="card-section">'
        + render_head_to_head(group)
        + "</div>"
        + render_extra_details(group)
        + "</article>"
    )


def render_group_header(league, league_payload, group):
    players = "".join(
        f'<span class="chip">{text(player)}</span>'
        for player in group.get("target", [])
    )

    return (
        '<div class="card-header">'
        '<div class="card-title-row">'
        "<div>"
        f'<p class="eyebrow">{text(group.get("group_id", ""))}</p>'
        f'<h3>{text(group.get("label", ""))}</h3>'
        "</div>"
        f'<span class="league-pill">{text(league)}</span>'
        "</div>"
        f'<div class="player-list">{players}</div>'
        '<div class="badge-row" style="margin-top: 12px">'
        f'{metadata_badge("Range", f"{league_payload.get("data_from", "-")} - {league_payload.get("data_to", "-")}")}'
        f'{metadata_badge("Files", league_payload.get("files_count", "-"))}'
        "</div>"
        "</div>"
    )


def render_group_metrics(group):
    return (
        '<div class="metrics-grid">'
        + metric("Exact Matches 5/5", group.get("coincidencias_5", 0))
        + metric("Matches >= 4/5", group.get("coincidencias_4", 0))
        + metric("Power Leader", first_name(group.get("power_ranking", [])))
        + metric("H2H Leader", first_name(group.get("h2h_ranking", [])))
        + "</div>"
    )


def first_name(rows):
    if not rows:
        return "-"

    return rows[0].get("player", "-")


def render_betting(group):
    betting = group.get("betting", {})
    back = betting.get("back", {})
    lay = betting.get("lay", {})

    return (
        '<div class="card-section">'
        "<h3>Betting Suggestion</h3>"
        '<div class="suggestion-grid" style="margin-top: 10px">'
        + render_suggestion("BACK", "back", back, "best_matchup_details")
        + render_suggestion("LAY", "lay", lay, "worst_matchup_details")
        + "</div>"
        "</div>"
    )


def render_suggestion(label, css_class, data, matchups_key):
    matchups = data.get(matchups_key, [])

    return (
        f'<div class="suggestion {css_class}">'
        f'<div class="suggestion-label">{text(label)}</div>'
        f'<div class="suggestion-player">{text(data.get("player", "-"))}</div>'
        '<div class="badge-row" style="margin-top: 8px">'
        f'{metadata_badge("Score", fmt_score(data.get("score")))}'
        f'{metadata_badge("Matches", data.get("matches", "-"))}'
        "</div>"
        + render_matchup_table(matchups)
        + "</div>"
    )


def render_matchup_table(rows):
    table_rows = [
        [
            row["rival"],
            row["W"],
            row["D"],
            row["L"],
            row["matches"],
            fmt_pct(row["win_pct"]),
            fmt_pct(row["draw_pct"]),
            fmt_pct(row["loss_pct"]),
        ]
        for row in rows
    ]

    return render_table(
        ["Rival", "W", "D", "L", "Matches", "W%", "D%", "L%"],
        table_rows,
        numeric_columns={1, 2, 3, 4, 5, 6, 7},
    )


def render_power_ranking(group):
    rows = [
        {
            "position": row["position"],
            "name": row["player"],
            "score": fmt_score(row["score"]),
        }
        for row in group.get("power_ranking", [])
    ]

    return render_rank_list("Power Ranking", rows)


def render_dominance(group):
    rows = [
        {
            "position": "",
            "name": row["player"],
            "score": f'{row["wins"]}/{row["rivals"]}',
        }
        for row in group.get("dominance", [])
    ]

    return render_rank_list("Dominance", rows)


def render_rank_list(title, rows):
    items = []

    for row in rows:
        items.append(
            '<div class="rank-row">'
            f'<span class="rank-pos">{text(row["position"])}</span>'
            f'<span class="rank-name">{text(row["name"])}</span>'
            f'<span class="rank-score">{text(row["score"])}</span>'
            "</div>"
        )

    return (
        "<div>"
        f"<h3>{text(title)}</h3>"
        f'<div class="rank-list">{"".join(items)}</div>'
        "</div>"
    )


def render_h2h_ranking(group):
    rows = [
        [
            row["player"],
            fmt_pct(row["score"]),
            row["matches"],
            fmt_score(row["weighted_score"]),
        ]
        for row in group.get("h2h_ranking", [])
    ]

    return (
        "<h3>H2H Ranking</h3>"
        + render_table(
            ["Player", "Score", "Matches", "Weighted"],
            rows,
            numeric_columns={1, 2, 3},
        )
    )


def render_totals(title, rows):
    table_rows = [
        [
            row["player"],
            row["W"],
            row["D"],
            row["L"],
            fmt_pct(row["win_pct"]),
            fmt_pct(row.get("loss_pct")),
        ]
        for row in rows
    ]

    if not table_rows:
        body = '<p class="section-subtitle">No rows for this group.</p>'
    else:
        body = render_table(
            ["Player", "W", "D", "L", "W%", "L%"],
            table_rows,
            numeric_columns={1, 2, 3, 4, 5},
        )

    return f"<h3>{text(title)}</h3>{body}"


def render_head_to_head(group):
    blocks = []

    for player_block in group.get("h2h_matrix", []):
        rows = [
            [
                rival["rival"],
                rival["W"],
                rival["D"],
                rival["L"],
                rival["matches"],
                fmt_pct(rival["win_pct"]),
                fmt_pct(rival["draw_pct"]),
                fmt_pct(rival["loss_pct"]),
            ]
            for rival in player_block.get("rivals", [])
        ]

        blocks.append(
            "<details>"
            f'<summary>{text(player_block.get("player", ""))}</summary>'
            + render_table(
                ["Rival", "W", "D", "L", "Matches", "W%", "D%", "L%"],
                rows,
                numeric_columns={1, 2, 3, 4, 5, 6, 7},
            )
            + "</details>"
        )

    return "<h3>Head to Head</h3>" + "".join(blocks)


def render_extra_details(group):
    return (
        '<div class="card-section">'
        "<h3>JSON Details</h3>"
        '<div class="badge-row" style="margin-top: 10px">'
        f'{metadata_badge("Target", ", ".join(group.get("target", [])))}'
        f'{metadata_badge("H2H Keys", ", ".join(group.get("h2h_keys", [])))}'
        f'{metadata_badge("Legacy Target", group.get("target_repr", ""))}'
        "</div>"
        "</div>"
    )


def render_table(headers, rows, numeric_columns=None, seq_columns=None, row_classes=None):
    numeric_columns = numeric_columns or set()
    seq_columns = seq_columns or set()

    header_html = "".join(f"<th>{text(header)}</th>" for header in headers)
    row_html = []

    for row_index, row in enumerate(rows):
        cells = []

        for index, value in enumerate(row):
            classes = []

            if index in numeric_columns:
                classes.append("num")

            if index in seq_columns:
                classes.append("seq")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            cells.append(f"<td{class_attr}>{text(value)}</td>")

        row_class = row_classes[row_index] if row_classes and row_index < len(row_classes) else ""
        class_attr = f' class="{text(row_class)}"' if row_class else ""
        row_html.append(f"<tr{class_attr}>{''.join(cells)}</tr>")

    return (
        '<div class="table-wrap">'
        "<table>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody>"
        "</table>"
        "</div>"
    )


def write_html(html):
    DOCS_DIR.mkdir(exist_ok=True)

    with open(DOCS_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    group_analysis = load_group_analysis()
    tracked_players = load_tracked_players(TRACKED_PLAYERS_FILE)
    coincident_config = load_coincident_config(TRACKED_PLAYERS_FILE)
    records = load_all_history()
    excluded_keys = excluded_player_keys(tracked_players)
    current_streaks = load_current_streaks(tracked_players, records)
    reference_time = datetime.now(timezone.utc)
    snapshot = calculate_operational_snapshot(
        records, tracked_players, reference_time=reference_time,
        excluded_keys=excluded_keys,
    )
    current_streaks_v2 = build_current_streaks_v2_payload(snapshot, reference_time=reference_time)
    coincident_pairs = calculate_all_coincident_pairs(
        records, snapshot=snapshot, reference_time=reference_time,
        window_hours=DEFAULT_OPERATIONAL_WINDOW_HOURS,
        excluded_keys=excluded_keys, tracked_players=tracked_players,
        manual_selected_keys=coincident_config["selected_keys"],
        excluded_candidate_keys=coincident_config["excluded_keys"],
    )
    html = render_page(
        group_analysis, current_streaks, coincident_pairs, current_streaks_v2,
    )

    write_html(html)

    print("HTML generado")


if __name__ == "__main__":
    main()
