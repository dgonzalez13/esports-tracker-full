import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

BASE_URL = "https://api.gtleagues.com/api/fixtures"

OUTPUT_DIR = BASE / "gt" / "data"

HEADERS = {
    "accept": "application/json",
    "origin": "https://www.gtleagues.com",
    "referer": "https://www.gtleagues.com/",
    "user-agent": "Mozilla/5.0"
}


# -------------------------
# RECUPERAR HISTÓRICO
# -------------------------
def get_date():

    if len(sys.argv) > 1:
        return datetime.strptime(
            sys.argv[1],
            "%d%m%Y"
        )

    return datetime.now()


# -------------------------
# RACHA ACTUAL SIN EMPATAR
# -------------------------
def current_no_draw_streak(seq):

    streak = 0

    for c in reversed(seq):

        if c == "E":
            break

        streak += 1

    return streak


# -------------------------
# RANGO DÍA (CORRECTO UTC)
# -------------------------
def get_day_range(date):
    tz = ZoneInfo("Europe/Madrid")

    start_local = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)

    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


def format_date(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# -------------------------
# API (PAGINACIÓN)
# -------------------------
def fetch_day(date):
    start, end = get_day_range(date)

    all_data = []
    offset = 0

    while True:
        params = {
            "kickoff": f"between:{format_date(start)},{format_date(end)}",
            "limit": 50,
            "offset": offset,
            "sort": "-kickoff,-matchNr",
            "status": "in:3,5,4,6",
            "xtc": "true"
        }

        r = requests.get(BASE_URL, params=params, headers=HEADERS)

        if r.status_code != 200:
            print(f"Error API: {r.status_code}")
            break

        data = r.json()

        if not data:
            break

        all_data.extend(data)
        offset += 50

        if len(data) < 50:
            break

    return all_data


# -------------------------
# PROCESADO
# -------------------------
def process(matches):
    stats = {}

    matches.sort(key=lambda x: x["kickoff"])

    for m in matches:
        try:
            home = next(p for p in m["participants"] if p["side"] == "home")
            away = next(p for p in m["participants"] if p["side"] == "away")

            p1 = home["participant"]["player"]["nickname"]
            p2 = away["participant"]["player"]["nickname"]

            s1 = m["result"]["stats"]["home_score"]
            s2 = m["result"]["stats"]["away_score"]

            for p in [p1, p2]:
                if p not in stats:
                    stats[p] = {
                        "W": 0, "D": 0, "L": 0,
                        "seq": [],
                        "vs": {},
                        "seen": set()
                    }

            match_id = m["id"]

            if match_id in stats[p1]["seen"]:
                continue

            stats[p1]["seen"].add(match_id)
            stats[p2]["seen"].add(match_id)

            # resultado
            if s1 > s2:
                res1, res2 = "V", "D"
                stats[p1]["W"] += 1
                stats[p2]["L"] += 1

            elif s1 < s2:
                res1, res2 = "D", "V"
                stats[p1]["L"] += 1
                stats[p2]["W"] += 1

            else:
                res1 = res2 = "E"
                stats[p1]["D"] += 1
                stats[p2]["D"] += 1

            stats[p1]["seq"].append(res1)
            stats[p2]["seq"].append(res2)

            # vs rivales
            for player, rival, res in [(p1, p2, res1), (p2, p1, res2)]:
                if rival not in stats[player]["vs"]:
                    stats[player]["vs"][rival] = {"W": 0, "D": 0, "L": 0, "seq": []}

                key = "W" if res == "V" else "D" if res == "E" else "L"
                stats[player]["vs"][rival][key] += 1
                stats[player]["vs"][rival]["seq"].append(res)

        except:
            continue

    return stats


# -------------------------
# OUTPUT
# -------------------------
def build_df(stats):
    rows = []
    vs_text = {}

    for p, s in stats.items():
        played = s["W"] + s["D"] + s["L"]

        seq = "".join(s["seq"])

        rows.append([
            p,
            s["W"], s["D"], s["L"],
            played,
            seq,
            current_no_draw_streak(seq)
        ])

        lines = []
        for rival, r in s["vs"].items():
            total = r["W"] + r["D"] + r["L"]
            if total == 0:
                continue

            w = round(r["W"] / total * 100, 1)
            d = round(r["D"] / total * 100, 1)
            l = round(r["L"] / total * 100, 1)

            h2h_seq = "".join(r["seq"])

            lines.append(f"{rival}: {total} ({w}%/{d}%/{l}%) [{h2h_seq}]")

        vs_text[p] = "\n".join(lines)

    df = pd.DataFrame(rows, columns=[
        "player", "W", "D", "L", "played", "seq", "current_streak"
    ])

    return df.sort_values("played", ascending=False), vs_text


# -------------------------
# SAVE
# -------------------------
def save_txt(df, vs_text, date):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = date.strftime("%Y%m%d") + "_player_stats.txt"
    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"ESTADÍSTICAS {date.strftime('%Y-%m-%d')}\n\n")
        f.write(f"{'player':<12} {'W':>3} {'D':>3} {'L':>3} {'played':>6} {'stk':>4} seq\n")

        for _, row in df.iterrows():
            f.write(
                f"{row['player']:<12} "
                f"{row['W']:>3} "
                f"{row['D']:>3} "
                f"{row['L']:>3} "
                f"{row['played']:>6} "
                f"{row['current_streak']:>4} "
                f"{row['seq']}\n"
            )

        f.write("\n\nVS RIVALES\n")

        for player in df["player"]:
            f.write(f"\n{player}\n")
            f.write(vs_text[player] + "\n")

    print(f"\n✔ Guardado en {path}")


# -------------------------
# MAIN
# -------------------------
def process_date(date, show_results=False):

    print(f"\nDescargando partidos de {date.date()}...")

    matches = fetch_day(date)

    print(f"Partidos encontrados: {len(matches)}")

    stats = process(matches)

    df, vs_text = build_df(stats)

    if show_results:

        print("\n🏆 RESULTADOS\n")

        for _, row in df.iterrows():
            print(
                f"{row['player']:<12} "
                f"{row['W']:>3} "
                f"{row['D']:>3} "
                f"{row['L']:>3} "
                f"{row['played']:>6} "
                f"{row['current_streak']:>3} "
                f"{row['seq']}"
            )

    save_txt(df, vs_text, date)


def main():

    today = datetime.now()

    yesterday = today - timedelta(days=1)

    # Repara ayer silenciosamente
    process_date(yesterday)

    # Muestra la clasificación actual
    process_date(today, show_results=True)


if __name__ == "__main__":
    main()