import os
import re
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import unicodedata
from bs4 import BeautifulSoup
import requests
from pathlib import Path

from match_history import (
    SCHEMA_VERSION,
    clean_name,
    name_key,
    perspective_id,
    result_pair,
    update_history,
    validate_perspective_pair,
)

BASE = Path(__file__).resolve().parent

OUTPUT_DIR = BASE / "eadriatic" / "data"
MATCH_HISTORY_FILE = OUTPUT_DIR / "match_history.jsonl"
EADRIATIC_URL = "https://eadriaticleague2.leaguerepublic.com/index.html"
EADRIATIC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}


def fetch_eadriatic_html():
    """Download the shared page used for both results and tracked players."""
    response = requests.get(EADRIATIC_URL, headers=EADRIATIC_HEADERS, timeout=30)
    response.raise_for_status()
    return response.text

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



def _split_group_heading(label):
    """Return block label and raw date text, accepting 4- or 3-digit years."""
    normalized = unicodedata.normalize("NFKC", label).strip()
    match = re.match(r"^(.*?)(\d{2}\.\d{2}\.\d{3,4})$", normalized)
    if not match:
        return None
    return match.group(1).strip(), match.group(2)


def _parse_complete_date(raw_date):
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw_date or ""):
        return None
    try:
        return datetime.strptime(raw_date, "%d.%m.%Y").date()
    except ValueError:
        return None


def _round_number(block_label):
    match = re.search(r"\bR(\d+)\b", block_label or "")
    return int(match.group(1)) if match else None


def _block_metadata(soup):
    """Collect fixture blocks and safely recover malformed dates/overnight rollovers."""
    blocks = []
    current = None

    for element in soup.find_all(["span", "tr"]):
        classes = element.get("class", [])
        if element.name == "span" and "fg-heading" in classes:
            split = _split_group_heading(element.get_text(strip=True))
            current = {
                "element_id": id(element),
                "raw_label": element.get_text(strip=True),
                "block_label": split[0] if split else None,
                "raw_date": split[1] if split else None,
                "match_date": _parse_complete_date(split[1]) if split else None,
                "times": [],
            }
            blocks.append(current)
            continue
        if element.name == "span" and "time-heading" in classes and current is not None:
            value = element.get_text(strip=True)
            if re.fullmatch(r"\d{2}:\d{2}", value):
                current["times"].append(datetime.strptime(value, "%H:%M").time())

    # Recover a three-digit year only from adjacent complete dates with the same prefix.
    for index, block in enumerate(blocks):
        raw_date = block["raw_date"]
        if block["match_date"] is not None or not re.fullmatch(r"\d{2}\.\d{2}\.\d{3}", raw_date or ""):
            continue

        candidates = []
        for neighbour_index in (index - 1, index + 1):
            if not 0 <= neighbour_index < len(blocks):
                continue
            neighbour_date = blocks[neighbour_index]["match_date"]
            if neighbour_date is None:
                continue
            candidate_text = neighbour_date.strftime("%d.%m.%Y")
            if candidate_text.startswith(raw_date):
                candidates.append(neighbour_date)

        unique_candidates = set(candidates)
        if len(unique_candidates) == 1:
            block["match_date"] = unique_candidates.pop()
            print(
                "WARNING: Recovered truncated EADRIATIC block date: "
                f"{raw_date} -> {block['match_date'].strftime('%d.%m.%Y')}"
            )

    # Some LeagueRepublic fixture blocks keep the date on which the round started,
    # even though their 00:xx/01:xx matches belong to the following calendar day.
    # Infer this only when consecutive rounds join chronologically within 8 hours.
    max_gap_seconds = 8 * 60 * 60
    for index in range(len(blocks) - 2, -1, -1):
        block = blocks[index]
        next_block = blocks[index + 1]
        if (
            block["match_date"] is None
            or next_block["match_date"] is None
            or not block["times"]
            or not next_block["times"]
        ):
            continue

        current_round = _round_number(block["block_label"])
        next_round = _round_number(next_block["block_label"])
        if current_round is None or next_round is None or next_round != current_round + 1:
            continue

        current_first = datetime.combine(block["match_date"], min(block["times"]))
        next_first = datetime.combine(next_block["match_date"], min(next_block["times"]))

        shifted_first = current_first + timedelta(days=1)
        shifted_gap = (next_first - shifted_first).total_seconds()

        if (
            next_block["match_date"] == block["match_date"] + timedelta(days=1)
            and 0 <= shifted_gap <= max_gap_seconds
        ):
            old_date = block["match_date"]
            block["match_date"] = old_date + timedelta(days=1)
            print(
                "WARNING: Recovered EADRIATIC midnight rollover: "
                f"{block['block_label']} {old_date.isoformat()} -> "
                f"{block['match_date'].isoformat()}"
            )

    return blocks


def _parse_group_heading(label, resolved_date=None):
    split = _split_group_heading(label)
    if not split:
        return None

    block_label, raw_date = split
    match_date = resolved_date or _parse_complete_date(raw_date)
    if match_date is None:
        return None

    detail = re.match(r"^(.*?)\s+R(\d+)\((.*?)\)$", block_label)
    if detail:
        round_name = f"{detail.group(1).strip()} R{detail.group(2)}"
        competition = detail.group(3).strip()
    else:
        round_name = block_label
        competition = None

    group_part = unicodedata.normalize("NFKC", block_label).casefold()
    group_part = re.sub(r"[^\w]+", "-", group_part, flags=re.UNICODE).strip("-")
    return {
        "match_date": match_date,
        "round": round_name,
        "competition": competition,
        "group_key": f"eadriatic:{group_part}:{match_date.isoformat()}",
    }


def parse_history_records(html, source_file, collected_at=None):
    """Extract finalized perspectives; EADRIATIC times are inferred as Madrid time."""
    soup = BeautifulSoup(html, "html.parser")
    block_dates = {
        block["element_id"]: block["match_date"]
        for block in _block_metadata(soup)
    }

    records = []
    seen_ids = set()
    current_block = None
    current_time = None
    block_order = -1
    row_order = 0

    for element in soup.find_all(["span", "tr"]):
        classes = element.get("class", [])
        if element.name == "span" and "fg-heading" in classes:
            block_order += 1
            current_block = _parse_group_heading(
                element.get_text(strip=True),
                resolved_date=block_dates.get(id(element)),
            )
            current_time = None
            row_order = 0
            continue
        if element.name == "span" and "time-heading" in classes:
            current_time = element.get_text(strip=True)
            continue
        if element.name != "tr" or not element.get("data-match-href"):
            continue

        source_row_order = row_order
        row_order += 1
        if current_block is None or not re.fullmatch(r"\d{2}:\d{2}", current_time or ""):
            continue

        href = element.get("data-match-href", "")
        id_match = re.fullmatch(r"/match/(\d+)\.html", href)
        cols = element.find_all("td")
        if not id_match or len(cols) < 3:
            continue

        score_match = re.search(r"(\d+)\s*-\s*(\d+)", cols[1].get_text(" ", strip=True))
        if not score_match:
            continue

        try:
            home_player = clean_name(extract_player(cols[0].get_text(strip=True)))
            away_player = clean_name(extract_player(cols[2].get_text(strip=True)))
        except (TypeError, ValueError):
            continue

        native_id = id_match.group(1)
        match_id = f"eadriatic:{native_id}"
        if match_id in seen_ids:
            continue
        seen_ids.add(match_id)

        home_score, away_score = map(int, score_match.groups())
        local_timestamp = datetime.combine(
            current_block["match_date"],
            datetime.strptime(current_time, "%H:%M").time(),
            tzinfo=ZoneInfo("Europe/Madrid"),
        )
        timestamp = local_timestamp.isoformat(timespec="minutes")
        timestamp_utc = local_timestamp.astimezone(ZoneInfo("UTC")).isoformat(
            timespec="minutes"
        ).replace("+00:00", "Z")
        home_result, away_result = result_pair(home_score, away_score)

        common = {
            "schema_version": SCHEMA_VERSION,
            "league": "EADRIATIC",
            "match_id": match_id,
            "native_match_id": native_id,
            "timestamp": timestamp,
            "timestamp_utc": timestamp_utc,
            "timestamp_precision": "minute",
            "timezone": "Europe/Madrid",
            "timezone_inferred": True,
            "home_score": home_score,
            "away_score": away_score,
            "source_type": "eadriatic_html",
            "source_file": source_file,
            "data_quality": "inferred",
            "round": current_block["round"],
            "group_key": current_block["group_key"],
            "source_block_order": block_order,
            "source_row_order": source_row_order,
        }
        if current_block["competition"]:
            common["competition"] = current_block["competition"]
        if collected_at is not None:
            common["collected_at"] = collected_at

        pair = []
        for player, rival, home_away, result in (
            (home_player, away_player, "home", home_result),
            (away_player, home_player, "away", away_result),
        ):
            pair.append({
                **common,
                "perspective_id": perspective_id(match_id, player),
                "player": player,
                "player_key": name_key(player),
                "rival": rival,
                "rival_key": name_key(rival),
                "result": result,
                "home_away": home_away,
            })

        validate_perspective_pair(pair)
        records.extend(pair)

    return records


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
                stats[player]["vs"][rival] = {"W": 0, "D": 0, "L": 0, "seq": []}

            key = "W" if res == "V" else "D" if res == "E" else "L"
            stats[player]["vs"][rival][key] += 1
            stats[player]["vs"][rival]["seq"].append(res)

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

            h2h_seq = "".join(r["seq"])

            lines.append(f"{rival}: {total} ({w}%/{d}%/{l}%) [{h2h_seq}]")

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
    print("Descargando HTML...")
    html = fetch_eadriatic_html()

    print(f"HTML descargado: {len(html):,} bytes")
    
    collected_at = datetime.now(ZoneInfo("Europe/Madrid"))
    backup_file = os.path.join(
        OUTPUT_DIR,
        collected_at.strftime("%Y%m%d") + "_eadriatic_downloaded.html"
    )

    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("Parseando HTML...")

    history_records = parse_history_records(
        html,
        source_file=Path(backup_file).name,
        collected_at=collected_at.isoformat(timespec="seconds"),
    )
    
    update_history(MATCH_HISTORY_FILE, history_records)
    print(f"Perspectivas guardadas en historial: {len(history_records)}")

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
