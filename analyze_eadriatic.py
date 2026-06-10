from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd
import os

BASE = Path(__file__).resolve().parent

# ============================================================
# CONFIG
# ============================================================

DATA_DIR = BASE / "eadriatic" / "data"
OUTPUT_DIR = BASE / "eadriatic" / "output"
MIN_PLAYED = 18
MAX_BETS = 8

# ============================================================
# ESTRUCTURAS
# ============================================================

player_totals = defaultdict(lambda: {
    "days": 0,
    "matches": 0,
    "wins": 0,
    "draws": 0,
    "losses": 0
})

daily_streak_rows = []

global_streak_counter = Counter()
global_streak_ended = Counter()
global_streak_finished_day = Counter()

daily_streak_counter = defaultdict(Counter)

streak_records = []
draw_records = []

# ============================================================
# FUNCIONES
# ============================================================

def parse_file(file_path):

    date = file_path.name[:8]

    rows = []

    inside_stats = False

    with open(file_path, "r", encoding="utf-8") as f:

        for line in f:

            line = line.rstrip()

            if "player" in line and "played" in line and "seq" in line:
                inside_stats = True
                continue

            if not inside_stats:
                continue

            if line.startswith("VS RIVALES"):
                break

            if not line.strip():
                continue

            parts = line.split()

            if len(parts) < 6:
                continue

            seq = parts[-1]

            if not seq:
                continue

            if not set(seq).issubset({"V", "E", "D"}):
                continue

            played = int(parts[-2])

            if played < MIN_PLAYED:
                continue

            losses = int(parts[-3])
            draws = int(parts[-4])
            wins = int(parts[-5])

            player = " ".join(parts[:-5])

            rows.append({
                "date": date,
                "player": player,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "played": played,
                "seq": seq
            })

    return rows


def analyze_streaks(seq):

    streaks = []

    current = 0

    for ch in seq:

        if ch == "E":

            if current > 0:
                streaks.append((current, True))

            current = 0

        else:
            current += 1

    ending_streak = current

    if current > 0:
        streaks.append((current, False))

    max_streak = max(
        [s[0] for s in streaks],
        default=0
    )

    return streaks, max_streak, ending_streak


# ============================================================
# CARGA
# ============================================================

import re

files = []

for f in Path(DATA_DIR).glob("*_eadriatic_player_stats.txt"):

    if re.match(r"^\d{8}_eadriatic_player_stats\.txt$", f.name):
        files.append(f)

files = sorted(files)

print(f"Archivos encontrados: {len(files)}")

print(f"Archivos: {len(files)}")

for file in files:

    day_rows = parse_file(file)

    for row in day_rows:

        player = row["player"]
        date = row["date"]
        seq = row["seq"]

        # ----------------------------------------
        # Totales jugador
        # ----------------------------------------

        player_totals[player]["days"] += 1
        player_totals[player]["matches"] += row["played"]
        player_totals[player]["wins"] += row["wins"]
        player_totals[player]["draws"] += row["draws"]
        player_totals[player]["losses"] += row["losses"]

        # ----------------------------------------
        # Rachas
        # ----------------------------------------

        streaks, max_streak, ending_streak = analyze_streaks(seq)

        daily_streak_rows.append({
            "date": date,
            "player": player,
            "played": row["played"],
            "draws": row["draws"],
            "max_no_draw_streak": max_streak,
            "ending_no_draw_streak": ending_streak
        })

        streak_records.append({
            "date": date,
            "player": player,
            "played": row["played"],
            "draws": row["draws"],
            "max_no_draw_streak": max_streak
        })

        draw_records.append({
            "date": date,
            "player": player,
            "played": row["played"],
            "draws": row["draws"]
        })

        # ----------------------------------------
        # Distribución rachas
        # ----------------------------------------

        seen_today = set()

        for length, ended_with_draw in streaks:

            if length < 9:
                continue

            global_streak_counter[length] += 1

            daily_streak_counter[date][length] += 1

            if ended_with_draw:
                global_streak_ended[length] += 1
            else:
                global_streak_finished_day[length] += 1

# ============================================================
# PLAYER SUMMARY
# ============================================================

player_rows = []

for player, p in player_totals.items():

    matches = p["matches"]
    wins = p["wins"]
    draws = p["draws"]
    losses = p["losses"]

    days = p["days"]

    player_rows.append({

        "player": player,

        "days": days,

        "matches": matches,

        "wins": wins,
        "draws": draws,
        "losses": losses,

        "win_pct": round(wins / matches * 100, 2),
        "draw_pct": round(draws / matches * 100, 2),
        "loss_pct": round(losses / matches * 100, 2),

        "avg_matches_day": round(matches / days, 2),

        "avg_wins_day": round(wins / days, 2),
        "avg_draws_day": round(draws / days, 2),
        "avg_losses_day": round(losses / days, 2)

    })

player_df = pd.DataFrame(player_rows)

os.makedirs(OUTPUT_DIR, exist_ok=True)

player_df.sort_values(
    "draw_pct",
    ascending=False
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "player_summary.csv"
    ),
    index=False
)

# ============================================================
# DAILY STREAKS
# ============================================================

pd.DataFrame(
    daily_streak_rows
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "daily_streaks.csv"
    ),
    index=False
)

# ============================================================
# PLAYER RISK ANALYSIS
# ============================================================

player_summary = pd.read_csv(os.path.join(
                                OUTPUT_DIR,
                                "player_summary.csv"
                            ))
daily_streaks = pd.read_csv(os.path.join(
                                OUTPUT_DIR,
                                "daily_streaks.csv"
                            ))

risk_rows = []

for player in player_summary["player"]:

    player_days = daily_streaks[
        daily_streaks["player"] == player
    ]

    max_streak = player_days["max_no_draw_streak"].max()
    
    draw_pct = player_summary.loc[
        player_summary["player"] == player,
        "draw_pct"
    ].iloc[0]
    
    matches = player_summary.loc[
        player_summary["player"] == player,
        "matches"
    ].iloc[0]

    streaks_18_plus = (
        player_days["max_no_draw_streak"] >= 18
    ).sum()

    streaks_20_plus = (
        player_days["max_no_draw_streak"] >= 20
    ).sum()

    streaks_22_plus = (
        player_days["max_no_draw_streak"] >= 22
    ).sum()

    streaks_25_plus = (
        player_days["max_no_draw_streak"] >= 25
    ).sum()
    
    danger_days_pct = round(
        (streaks_18_plus / len(player_days)) * 100,
        2
    )
    
    stability_score = (
        streaks_18_plus * 1
        + streaks_20_plus * 2
        + streaks_22_plus * 3
        + streaks_25_plus * 4
    )

    if stability_score == 0:
        stability = "VERY_HIGH"

    elif stability_score <= 2:
        stability = "HIGH"

    elif stability_score <= 5:
        stability = "MEDIUM"

    else:
        stability = "LOW"
    
    recommended_entry = max(
        8,
        max_streak - MAX_BETS + 1
    )

    safe_for_strategy = (
        "YES"
        if max_streak <= (recommended_entry + MAX_BETS - 1)
        else "NO"
    )

    risk_rows.append({

        "player": player,

        "days_analyzed":
            len(player_days),

        "matches_analyzed":
            matches,

        "draw_pct": draw_pct,

        "max_streak": max_streak,

        "avg_max_streak":
            round(
                player_days["max_no_draw_streak"].mean(),
                2
            ),

        "streaks_18_plus": streaks_18_plus,
        "streaks_20_plus": streaks_20_plus,
        "streaks_22_plus": streaks_22_plus,
        "streaks_25_plus": streaks_25_plus,
            
        "recommended_entry":
            recommended_entry,

        "max_bets":
            MAX_BETS,

        "safe_for_strategy":
            safe_for_strategy,
            
        "danger_days_pct":
            danger_days_pct,

        "stability":
            stability,

    })

risk_df = pd.DataFrame(risk_rows)

risk_df = risk_df.sort_values(
    ["recommended_entry", "danger_days_pct", "draw_pct"],
    ascending=[True, True, False]
)

risk_df.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "player_risk_analysis.csv"
    ),
    index=False
)

# ============================================================
# GLOBAL STREAK DISTRIBUTION
# ============================================================

global_rows = []

for streak in sorted(global_streak_counter):

    global_rows.append({

        "streak": streak,

        "total_occurrences":
            global_streak_counter[streak],

        "ended_same_day":
            global_streak_ended[streak],

        "finished_day_with_streak":
            global_streak_finished_day[streak]

    })

pd.DataFrame(
    global_rows
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "streak_distribution_global.csv"
    ),
    index=False
)

# ============================================================
# DAILY STREAK DISTRIBUTION
# ============================================================

daily_rows = []

for date in sorted(daily_streak_counter):

    for streak in sorted(daily_streak_counter[date]):

        daily_rows.append({

            "date": date,

            "streak": streak,

            "occurrences":
                daily_streak_counter[date][streak]

        })

pd.DataFrame(
    daily_rows
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "streak_distribution_by_day.csv"
    ),
    index=False
)

# ============================================================
# DAILY STREAK SUMMARY
# ============================================================

summary_rows = []

for date in sorted(daily_streak_counter):

    row = {"date": date}

    for streak in range(9, 31):

        row[f"streak_{streak}"] = \
            daily_streak_counter[date][streak]

    summary_rows.append(row)

pd.DataFrame(
    summary_rows
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "daily_streak_summary.csv"
    ),
    index=False
)

# ============================================================
# STREAK RECORDS
# ============================================================

pd.DataFrame(
    streak_records
).sort_values(
    "max_no_draw_streak",
    ascending=False
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "streak_records.csv"
    ),
    index=False
)

# ============================================================
# DRAW RECORDS
# ============================================================

draw_df = pd.DataFrame(draw_records)

draw_df.sort_values(
    ["draws", "played"],
    ascending=[True, False]
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "draw_records_lowest.csv"
    ),
    index=False
)

draw_df.sort_values(
    ["draws", "played"],
    ascending=[False, False]
).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "draw_records_highest.csv"
    ),
    index=False
)

print()
print("CSV generados:")
print(" - player_summary.csv")
print(" - daily_streaks.csv")
print(" - streak_distribution_global.csv")
print(" - streak_distribution_by_day.csv")
print(" - daily_streak_summary.csv")
print(" - streak_records.csv")
print(" - draw_records_lowest.csv")
print(" - draw_records_highest.csv")