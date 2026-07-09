import json
from html import escape
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
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


def load_tracked_players():
    tracked = set()

    with open(TRACKED_PLAYERS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            league, player = line.split("|", 1)

            tracked.add((
                league.strip().upper(),
                player.strip().lower()
            ))

    return tracked
    
    
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
    
    
def load_current_streaks():
    streaks = {}
    tracked_players = load_tracked_players()

    for league, config in LEAGUES.items():
        stats_file = latest_stats_file(config["data_dir"])
        stats = load_daily_stats(stats_file)

        rows = []

        for row in stats:
        
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
                "tracked": (league, row["player"].lower()) in tracked_players,
                "balance":
                    "🟢"
                    if (league, row["player"].lower()) in tracked_players
                    and row["W"] >= row["D"] + row["L"]
                    else
                    "🔴"
                    if (league, row["player"].lower()) in tracked_players
                    and row["L"] >= row["W"] + row["D"]
                    else
                    "",
            })

        streaks[league] = {
            "title": config["title"],
            "source": stats_file.name if stats_file else "",
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


def render_page(data, current_streaks):
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
    {render_current_streaks(current_streaks)}
    {render_group_dashboard(data)}
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
</style>"""


def metadata_badge(label, value):
    return f'<span class="badge">{text(label)}: {text(value)}</span>'


def render_current_streaks(current_streaks):
    panels = [
        render_streak_panel(league, payload)
        for league, payload in current_streaks.items()
    ]

    return (
        '<section class="dashboard-section">'
        '<div class="section-head">'
        "<div>"
        "<h2>Current Streaks</h2>"
        '<p class="section-subtitle">Latest daily player files, with tracked player highlights and current win/loss streaks.</p>'
        "</div>"
        "</div>"
        f'<div class="streak-grid">{"".join(panels)}</div>'
        "</section>"
    )


def render_streak_panel(league, payload):
    rows = payload["rows"]

    def render_streak_table(rows):

        html = []

        html.append('<div class="table-wrap"><table>')

        html.append("""
        <thead>
        <tr>
            <th>PLAYER</th>
            <th></th>
            <th>W</th>
            <th>D</th>
            <th>L</th>
            <th>PLAYED</th>
            <th>STK WIN</th>
            <th>STK LOSE</th>
            <th>SEQ</th>
        </tr>
        </thead>
        <tbody>
        """)

        for row in rows:

            style = (
                ' style="background:#e8f7ee;font-weight:bold;"'
                if row["tracked"]
                else ""
            )

            html.append(f"<tr{style}>")

            html.append(f"<td>{text(row['player'])}</td>")
            html.append(f"<td>{row['balance']}</td>")
            html.append(f'<td class="num">{row["W"]}</td>')
            html.append(f'<td class="num">{row["D"]}</td>')
            html.append(f'<td class="num">{row["L"]}</td>')
            html.append(f'<td class="num">{row["played"]}</td>')
            html.append(f'<td class="num">{row["stk_win"]}</td>')
            html.append(f'<td class="num">{row["stk_lose"]}</td>')
            html.append(f'<td class="seq">{row["seq"]}</td>')

            html.append("</tr>")

        html.append("</tbody></table></div>")

        return "".join(html)

    return (
        '<article class="streak-panel">'
        '<div class="league-head">'
        f'<h3>{text(payload["title"])}</h3>'
        f'{metadata_badge("Source", payload["source"])}'
        "</div>"
        + render_streak_table(rows)
        + "</article>"
    )


def render_group_dashboard(data):
    leagues = data.get("leagues", {})
    sections = []

    for league, payload in leagues.items():
        sections.append(render_league_groups(league, payload))

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


def render_league_groups(league, payload):
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
        + render_h2h_alerts(payload.get("h2h_alerts", []))
        + f'<div class="cards-grid">{"".join(cards)}</div>'
        "</div>"
    )



def render_h2h_alerts(alerts):
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
        "<th>Group</th>"
        "<th>Player</th>"
        "<th>Rival</th>"
        "<th>W</th>"
        "<th>D</th>"
        "<th>L</th>"
        "<th>Matches</th>"
        "<th>Win%</th>"
        "<th>Signal</th>"
        "<th>Confidence</th>"
        "</tr></thead><tbody>"
    )

    for alert in alerts:
        confidence = alert.get("confidence", "")
        signal = alert.get("signal", "")
        is_low_sample = alert.get("low_sample", confidence == "LOW SAMPLE")

        row_class = ' class="low-sample-row"' if is_low_sample else ""

        signal_class = (
            "signal-strong"
            if signal == "STRONG"
            else "signal-watch"
        )

        confidence_class = (
            "confidence-low"
            if is_low_sample
            else "confidence-high"
        )

        signal_label = (
            "🟢 STRONG"
            if signal == "STRONG"
            else "🟡 WATCH"
        )

        confidence_label = (
            "⚠️ LOW SAMPLE"
            if is_low_sample
            else "✅ HIGH"
        )

        html.append(f"<tr{row_class}>")
        html.append(f"<td>{text(alert.get('group', ''))}</td>")
        html.append(f"<td>{text(alert.get('player', ''))}</td>")
        html.append(f"<td>{text(alert.get('rival', ''))}</td>")
        html.append(f'<td class="num">{text(alert.get("W", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("D", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("L", ""))}</td>')
        html.append(f'<td class="num">{text(alert.get("matches", ""))}</td>')
        html.append(f'<td class="num">{text(fmt_pct(alert.get("win_pct")))}</td>')
        html.append(
            '<td>'
            f'<span class="signal-badge {signal_class}">'
            f"{text(signal_label)}"
            "</span>"
            "</td>"
        )
        html.append(
            '<td>'
            f'<span class="confidence-badge {confidence_class}">'
            f"{text(confidence_label)}"
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


def render_table(headers, rows, numeric_columns=None, seq_columns=None):
    numeric_columns = numeric_columns or set()
    seq_columns = seq_columns or set()

    header_html = "".join(f"<th>{text(header)}</th>" for header in headers)
    row_html = []

    for row in rows:
        cells = []

        for index, value in enumerate(row):
            classes = []

            if index in numeric_columns:
                classes.append("num")

            if index in seq_columns:
                classes.append("seq")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            cells.append(f"<td{class_attr}>{text(value)}</td>")

        row_html.append(f"<tr>{''.join(cells)}</tr>")

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
    current_streaks = load_current_streaks()
    html = render_page(group_analysis, current_streaks)

    write_html(html)

    print("HTML generado")


if __name__ == "__main__":
    main()
