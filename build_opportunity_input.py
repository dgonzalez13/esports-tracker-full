from pathlib import Path
from collections import defaultdict
import pandas as pd
import sys

BASE = Path(__file__).resolve().parent

TRACKED_ONLY = True

if len(sys.argv) > 1 and sys.argv[1].lower() == "all":
    TRACKED_ONLY = False

# --------------------------------------------------
# TRACKED PLAYERS
# --------------------------------------------------

tracked_players = set()

tracked_file = BASE / "tracked_players.txt"

if tracked_file.exists():

    with open(tracked_file, "r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            if "|" in line:

                league, player = line.split("|", 1)

                tracked_players.add(
                    (
                        league.strip().upper(),
                        player.strip().lower()
                    )
                )


# --------------------------------------------------
# PARSE
# --------------------------------------------------

def parse_file(file_path):

    rows = []
    inside_stats = False

    with open(file_path, "r", encoding="utf-8") as f:

        for line in f:

            line = line.rstrip()

            if (
                "player" in line
                and "played" in line
                and "seq" in line
            ):
                inside_stats = True
                continue

            if not inside_stats:
                continue

            if line.startswith("VS RIVALES"):
                break

            if not line.strip():
                continue

            parts = line.split()

            if len(parts) < 2:
                continue

            seq = parts[-1]

            if not set(seq).issubset({"V", "E", "D"}):
                continue

            i = len(parts) - 2

            while i >= 0 and parts[i].isdigit():
                i -= 1

            player = " ".join(parts[: i + 1]).strip()

            if not player:
                continue

            rows.append({
                "player": player,
                "seq": seq
            })

    return rows

# --------------------------------------------------
# BUILD SEQUENCES
# --------------------------------------------------

player_sequences = {}

leagues = [
    (
        "GT",
        BASE / "gt" / "data",
        "*_player_stats.txt"
    ),
    (
        "EADRIATIC",
        BASE / "eadriatic" / "data",
        "*_eadriatic_player_stats.txt"
    )
]

for league, folder, pattern in leagues:

    if not folder.exists():
        continue

    files = sorted(folder.glob(pattern))

    print(
        f"{league}: {len(files)} archivos"
    )

    seqs = defaultdict(str)

    for file in files:

        for row in parse_file(file):

            seqs[row["player"]] += row["seq"]

    player_sequences[league] = seqs

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def current_streak(seq):

    s = 0

    for ch in reversed(seq):

        if ch == "E":
            break

        s += 1

    return s


def max_streak(seq):

    s = 0
    m = 0

    for ch in seq:

        if ch == "E":
            s = 0
        else:
            s += 1
            m = max(m, s)

    return m


def avg_streak(seq):

    streaks = []
    streak = 0

    for ch in seq:

        if ch == "E":

            if streak > 0:
                streaks.append(streak)

            streak = 0

        else:
            streak += 1

    if streak > 0:
        streaks.append(streak)

    if not streaks:
        return 0

    return round(
        sum(streaks) / len(streaks),
        2
    )
    

def analyse_entry(seq, entry):

    samples = 0
    hits = 0

    streak = 0

    for i, ch in enumerate(seq):

        if ch == "E":
            streak = 0
            continue

        streak += 1

        if streak == entry:

            samples += 1

            found = False

            for j in range(1, 9):

                if i + j >= len(seq):
                    break

                if seq[i + j] == "E":
                    found = True
                    break

            if found:
                hits += 1

    prob = 0

    if samples:
        prob = round(
            hits / samples * 100,
            2
        )

    return samples, prob

# --------------------------------------------------
# BUILD CSV
# --------------------------------------------------

rows = []

for league, seqs in player_sequences.items():

    for player, seq in seqs.items():

        if (
            TRACKED_ONLY
            and tracked_players
            and (
                league.upper(),
                player.lower()
            ) not in tracked_players
        ):
            continue

        matches = len(seq)
        draws = seq.count("E")

        draw_pct = round(
            draws / matches * 100,
            2
        )

        current = current_streak(seq)

        avg = avg_streak(seq)

        samples, prob = analyse_entry(
            seq,
            current
        )

        rows.append({
            "league": league,
            "player": player,

            "matches": matches,
            "draws": draws,
            "draw_pct": draw_pct,

            "current_streak_real": current,

            "avg_streak": avg,

            "samples": samples,

            "prob_next_8": prob
        })

df = pd.DataFrame(rows)

print("ROWS:", len(rows))

if rows:
    print(rows[0])

if df.empty:
    print("No se encontró ningún jugador.")
    sys.exit()


# -----------------------------------------
# RECOMMENDATION
# -----------------------------------------

def recommendation(row):

    # Apostar

    if (
        row["draw_pct"] >= 17
        and row["prob_next_8"] >= 85
        and row["samples"] >= 30
        and row["current_streak_real"] >= row["avg_streak"]
    ):
        return "BET"

    # Vigilar

    if (
        row["draw_pct"] >= 15
        and row["prob_next_8"] >= 80
        and row["samples"] >= 20
    ):
        return "WATCH"

    return "SKIP"
    

def reason(row):

    reasons = []

    if row["draw_pct"] >= 17:
        reasons.append("DRAW_OK")

    if row["prob_next_8"] >= 85:
        reasons.append("PROB_OK")

    if row["samples"] >= 30:
        reasons.append("SAMPLES_OK")

    if row["current_streak_real"] >= row["avg_streak"]:
        reasons.append("STREAK_OK")

    return "|".join(reasons)

df["reason"] = df.apply(reason, axis=1)


df["recommendation"] = df.apply(
    recommendation,
    axis=1
)

stake = 0.1

martingale_cost = (
    stake +
    stake * 2 +
    stake * 4 +
    stake * 8 +
    stake * 16 +
    stake * 32 +
    stake * 64 +
    stake * 128
)

martingale_profit = stake

# -----------------------------------------
# SORT
# -----------------------------------------


print(df.head(10))

output = BASE / "opportunity_input.csv"

df.to_csv(
    output,
    index=False
)

print()
print("Generado:")
print(output)
print("Registros:", len(df))