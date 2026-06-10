import os
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from pathlib import Path

BASE = Path(__file__).resolve().parent

OUTPUT_DIR = r"C:\apuestas\eadriatic\data"

OUTPUT_DIR = BASE / "eadriatic" / "data"

# -------------------------
# EXTRAER JUGADOR (ROBUSTO)
# -------------------------
def extract_player(name):
    """
    Solo acepta:
    Equipo (Jugador)

    Ignora:
    Jugador (Equipo Esport)
    """

    if "(" not in name or ")" not in name:
        return None

    inside = name.split("(")[1].replace(")", "").strip()

    # Si dentro pone "esport", es el formato duplicado
    if "esport" in inside.lower():
        return None

    return inside


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
# PARSE HTML
# -------------------------
def parse_matches(html):
    soup = BeautifulSoup(html, "html.parser")

    matches = []
    seen_ids = set()

    rows = soup.select("tr[data-match-href]")
    
    print("Rows HTML:", len(rows))

    for row in rows:
    
        match_id = row.get("data-match-href")

        if match_id in seen_ids:
            continue

        seen_ids.add(match_id)   
    
        cols = row.find_all("td")

        if len(cols) < 3:
            continue

        try:
            raw_p1 = cols[0].get_text(strip=True)
            raw_p2 = cols[2].get_text(strip=True)

            p1 = extract_player(raw_p1)
            p2 = extract_player(raw_p2)

            # ignorar filas inválidas
            if not p1 or not p2:
                continue

            score_text = cols[1].get_text(" ", strip=True)

            m = re.search(r"(\d+)\s*-\s*(\d+)", score_text)
            if not m:
                continue

            s1 = int(m.group(1))
            s2 = int(m.group(2))

            matches.append((p1, s1, s2, p2))

        except:
            continue

    print("Matches únicos:", len(matches))
    
    return matches


# -------------------------
# PROCESAR ESTADÍSTICAS
# -------------------------
def process(matches):
    stats = {}

    # orden cronológico (clave para secuencia)
    # matches = list(reversed(matches))

    for p1, s1, s2, p2 in matches:

        for p in [p1, p2]:
            if p not in stats:
                stats[p] = {
                    "W": 0, "D": 0, "L": 0,
                    "seq": [],
                    "vs": {}
                }

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

        # VS rivales
        for player, rival, res in [(p1, p2, res1), (p2, p1, res2)]:
            if rival not in stats[player]["vs"]:
                stats[player]["vs"][rival] = {"W": 0, "D": 0, "L": 0}

            key = "W" if res == "V" else "D" if res == "E" else "L"
            stats[player]["vs"][rival][key] += 1

    return stats


# -------------------------
# DATAFRAME + VS
# -------------------------
def build_df(stats):
    rows = []
    vs_text = {}

    for p, s in stats.items():
        played = s["W"] + s["D"] + s["L"]

        #seq = "".join(s["seq"]).rjust(25)
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

            lines.append(f"{rival}: {total} ({w}%/{d}%/{l}%)")

        vs_text[p] = "\n".join(lines)

    df = pd.DataFrame(rows, columns=[
        "player", "W", "D", "L", "played", "seq", "current_streak"
    ])

    return df.sort_values("played", ascending=False), vs_text


# -------------------------
# GUARDAR TXT (FORMATO GT)
# -------------------------
def save_txt(df, vs_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.now()
    filename = today.strftime("%Y%m%d") + "_eadriatic_player_stats.txt"
    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"ESTADÍSTICAS {today.strftime('%Y-%m-%d')}\n\n")

        #f.write(df.to_string(index=False))
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
def main():

    URL = "https://eadriaticleague2.leaguerepublic.com/index.html"

    print("Descargando HTML...")

    response = requests.get(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0 Safari/537.36"
            )
        },
        timeout=30
    )

    response.raise_for_status()

    html = response.text

    print(f"HTML descargado: {len(html):,} bytes")
    
    backup_file = os.path.join(
        OUTPUT_DIR,
        datetime.now().strftime("%Y%m%d") + "_eadriatic_downloaded.html"
    )

    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("Parseando HTML...")

    matches = parse_matches(html)

    print("Partidos encontrados:", len(matches))
    
    from collections import Counter

    c = Counter(matches)

    duplicados = sum(1 for v in c.values() if v > 1)

    print("Partidos duplicados:", duplicados)

    stats = process(matches)

    df, vs_text = build_df(stats)

    print("\n🏆 RESULTADOS\n")
    #print(df)
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

    print(repr(df.iloc[0]["seq"]))
    print(len(df.iloc[0]["seq"]))

    save_txt(df, vs_text)


if __name__ == "__main__":
    main()