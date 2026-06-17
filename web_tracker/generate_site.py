import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def load_daily_stats(txt_file):
    rows = []

    with open(txt_file, encoding="utf-8") as f:
        lines = f.readlines()

    in_table = False

    for line in lines:

        if line.startswith("player"):
            in_table = True
            continue

        if in_table:

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
                "seq": parts[6]
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(
            "played",
            ascending=False
        )

    return df


# =========================
# OBTENER ÚLTIMO TXT POR FECHA
# =========================

def latest_stats_file(folder):

    files = list(folder.glob("*player_stats.txt"))

    return max(
        files,
        key=lambda p: p.name[:8]
    )


# =========================
# HISTÓRICO
# =========================

gt = pd.read_csv(
    BASE / "gt" / "output" / "player_risk_analysis.csv"
)

ead = pd.read_csv(
    BASE / "eadriatic" / "output" / "player_risk_analysis.csv"
)

opportunities = pd.read_csv(
    BASE / "opportunity_input.csv"
)

# =========================
# RANKING DIARIO GT
# =========================

gt_txt = latest_stats_file(
    BASE / "gt" / "data"
)

gt_today = load_daily_stats(gt_txt)


# =========================
# RANKING DIARIO EADRIATIC
# =========================

ead_txt = latest_stats_file(
    BASE / "eadriatic" / "data"
)

ead_today = load_daily_stats(ead_txt)


# =========================
# TRACKED PLAYERS
# =========================

tracked_file = BASE / "tracked_players.txt"

tracked_rows = []

tracked_players_set = set()

if tracked_file.exists():

    with open(tracked_file, encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line or "|" not in line:
                continue

            league, player = line.split("|", 1)

            league = league.strip().lower()
            player = player.strip()
            
            tracked_players_set.add(
                (
                    league.upper(),
                    player.lower()
                )
            )

            if league == "gt":

                hist = gt[
                    gt["player"].str.lower() == player.lower()
                ]

                today = gt_today[
                    gt_today["player"].str.lower() == player.lower()
                ]

            elif league == "eadriatic":

                hist = ead[
                    ead["player"].str.lower() == player.lower()
                ]

                today = ead_today[
                    ead_today["player"].str.lower() == player.lower()
                ]

            else:
                continue

            if hist.empty or today.empty:
                continue

            entry = int(hist.iloc[0]["recommended_entry"])
            streak = int(today.iloc[0]["stk"])

            remaining = max(
                0,
                entry - streak
            )

            if streak < entry:

                stake = "-"

            else:

                step = streak - entry

                stake = round(
                    0.1 * (2 ** step),
                    2
                )

            tracked_rows.append({
                "league": league.upper(),
                "player": player,
                "rating": hist.iloc[0]["stability"],
                "current_streak": streak,
                "entry": entry,
                "remaining": (
                    "READY"
                    if remaining == 0
                    else remaining
                ),
                "stake": stake
            })

opportunities["player_lower"] = (
    opportunities["player"]
    .str.strip()
    .str.lower()
)

opportunities = opportunities[
    opportunities.apply(
        lambda r: (
            r["league"],
            r["player_lower"]
        ) in tracked_players_set,
        axis=1
    )
]

opportunities = opportunities.drop(
    columns=["player_lower"]
)

priority = {
    "BET": 0,
    "WATCH": 1,
    "SKIP": 2
}

opportunities["_sort"] = (
    opportunities["recommendation"]
    .map(priority)
)

opportunities = opportunities.sort_values(
    ["_sort", "prob_next_8", "samples"],
    ascending=[True, False, False]
).drop(columns="_sort")


tracked_df = pd.DataFrame(tracked_rows)

if not tracked_df.empty:

    tracked_df["_sort"] = tracked_df["remaining"].apply(
        lambda x: 0 if x == "READY" else int(x)
    )

    tracked_df = tracked_df.sort_values(
        "_sort"
    ).drop(
        columns="_sort"
    )

html = f"""
<html>

<head>
<meta charset="utf-8">
<title>eSports Tracker</title>

<style>

body {{
    font-family: Arial, sans-serif;
    margin: 30px;
}}

table {{
    border-collapse: collapse;
    margin-bottom: 25px;
}}

th, td {{
    border: 1px solid #ccc;
    padding: 6px 10px;
    text-align: center;
}}

th {{
    background: #f0f0f0;
}}

table td:last-child {{
    text-align: left;
    font-family: Consolas, monospace;
}}

</style>

</head>

<body>

<h1>🎯 Betting Opportunities</h1>

{
    opportunities[
        [
            "league",
            "player",
            "draw_pct",
            "current_streak_real",
            "avg_streak",
            "samples",
            "prob_next_8",
            "recommendation"
        ]
    ].to_html(index=False)
}

<hr>

<h1>🎯 Tracked Players</h1>

{
    tracked_df.to_html(index=False)
    if not tracked_df.empty
    else "<p>No tracked players found.</p>"
}

<hr>

<h1>GT League</h1>

<h2>Current Streaks</h2>

{gt_today.to_html(index=False)}

<h2>Historical Analysis</h2>

{gt[
    [
        "player",
        "draw_pct",
        "max_streak",
        "recommended_entry",
        "danger_days_pct",
        "stability"
    ]
].head(200).to_html(index=False)}

<hr>

<h1>Eadriatic League</h1>

<h2>Current Streaks</h2>

{ead_today.to_html(index=False)}

<h2>Historical Analysis</h2>

{ead[
    [
        "player",
        "draw_pct",
        "max_streak",
        "recommended_entry",
        "danger_days_pct",
        "stability"
    ]
].head(200).to_html(index=False)}

</body>
</html>
"""

docs_dir = BASE / "docs"
docs_dir.mkdir(exist_ok=True)

with open(
    docs_dir / "index.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

print("HTML generado")