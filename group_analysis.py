from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import sys
import re


BASE = Path(__file__).resolve().parent
JSON_OUTPUT = BASE / "group_analysis.json"
H2H_ALERT_THRESHOLD = 48
MIN_H2H_ALERT_MATCHES = 20


def empty_record():
    return {"W": 0, "D": 0, "L": 0, "seq": []}


def nested_h2h():
    return defaultdict(lambda: defaultdict(empty_record))


def load_groups():

    groups = {
        "GT": [],
        "EADRIATIC": []
    }

    current = []

    with open(
        BASE / "tracked_players.txt",
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            league, player = line.split("|")

            current.append(player)

            if len(current) == 5:

                groups[league].append(
                    current.copy()
                )

                current = []

    return groups


def parse_vs_rivals(file_path):

    players = {}

    current_player = None
    inside = False

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.rstrip()

            if line.startswith("VS RIVALES"):
                inside = True
                continue

            if not inside:
                continue

            if not line:
                continue

            if ":" not in line:

                current_player = line.strip()

                if current_player:
                    players[current_player] = {}

                continue

            if current_player is None:
                continue

            m = re.match(
                r"^(.*?):\s+(\d+)\s+\(([\d\.]+)%/([\d\.]+)%/([\d\.]+)%\)"
                r"(?:\s+\[([VED]*)\])?$",
                line
            )

            if not m:
                continue

            rival = m.group(1).strip()

            matches = int(m.group(2))

            w_pct = float(m.group(3))
            d_pct = float(m.group(4))
            l_pct = float(m.group(5))

            wins = round(matches * w_pct / 100)
            draws = round(matches * d_pct / 100)
            losses = matches - wins - draws
            sequence = m.group(6) or ""

            players[current_player][rival] = {
                "W": wins,
                "D": draws,
                "L": losses,
                "seq": list(sequence)
            }

    return players


def build_groups(players):

    groups = []

    used = set()

    for player, rivals in players.items():

        if player in used:
            continue

        candidate = (
            {player}
            | set(rivals.keys())
        )

        valid = True

        for p in candidate:

            if p not in players:
                valid = False
                break

            expected = candidate - {p}

            if not expected.issubset(
                set(players[p].keys())
            ):
                valid = False
                break

        if valid:

            groups.append(candidate)

            used.update(candidate)

    return groups


def parse_summary(file_path):

    stats = {}

    inside = False

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.rstrip()

            if (
                "player" in line
                and "played" in line
                and "seq" in line
            ):
                inside = True
                continue

            if not inside:
                continue

            if line.startswith(
                "VS RIVALES"
            ):
                break

            if not line.strip():
                continue

            parts = line.split()

            if len(parts) < 5:
                continue

            seq = parts[-1]

            if not set(seq).issubset(
                {"V", "E", "D"}
            ):
                continue

            player = " ".join(
                parts[:-5]
            ).strip()

            try:

                w = int(parts[-5])
                d = int(parts[-4])
                l = int(parts[-3])

            except:

                continue

            stats[player] = {
                "W": w,
                "D": d,
                "L": l
            }

    return stats


def data_dir_for(league):
    if league == "GT":
        return BASE / "gt" / "data"

    return BASE / "eadriatic" / "data"


def add_record(target, source):
    target["W"] += source["W"]
    target["D"] += source["D"]
    target["L"] += source["L"]

    if source.get("seq"):
        target["seq"].extend(source["seq"])


def totals_rows(totals):
    rows = []

    for player, s in sorted(
        totals.items()
    ):

        played = (
            s["W"]
            + s["D"]
            + s["L"]
        )

        win_pct = (
            s["W"]
            / played
            * 100
            if played
            else 0
        )

        loss_pct = (
            s["L"]
            / played
            * 100
            if played
            else 0
        )

        rows.append({
            "player": player,
            "W": s["W"],
            "D": s["D"],
            "L": s["L"],
            "win_pct": win_pct,
            "loss_pct": loss_pct
        })

    return rows


def pct(value, total):
    if total == 0:
        return 0

    return value / total * 100


def consecutive_wins(sequence):
    streak = 0

    for result in reversed(sequence):
        if result != "V":
            break

        streak += 1

    return streak


def consecutive_without_loss(sequence):
    streak = 0

    for result in reversed(sequence):
        if result == "D":
            break

        streak += 1

    return streak


def matchup_record(rival, stats):
    total = (
        stats["W"]
        + stats["D"]
        + stats["L"]
    )

    sequence = "".join(stats.get("seq", []))

    return {
        "rival": rival,
        "W": stats["W"],
        "D": stats["D"],
        "L": stats["L"],
        "matches": total,
        "win_pct": pct(stats["W"], total),
        "draw_pct": pct(stats["D"], total),
        "loss_pct": pct(stats["L"], total),
        "seq": sequence,
        "last5": sequence[-5:],
        "last10": sequence[-10:],
        "stk_win": consecutive_wins(sequence),
        "stk_lose": consecutive_without_loss(sequence)
    }


def files_metadata(files):
    names = [file.name for file in files]
    dates = [
        name[:8]
        for name in names
        if re.match(r"^\d{8}", name)
    ]

    return {
        "files": names,
        "files_count": len(files),
        "data_from": min(dates) if dates else None,
        "data_to": max(dates) if dates else None
    }


def calculate_power_ranking(target, h2h):
    ranking = []

    for player in target:

        score = 0

        for rival in target:

            if player == rival:
                continue

            s = h2h[player][rival]

            total = (
                s["W"]
                + s["D"]
                + s["L"]
            )

            if total == 0:
                continue

            win_pct = (
                s["W"]
                / total
                * 100
            )

            score += (
                win_pct - 50
            )

        ranking.append(
            (player, score)
        )

    ranking.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return ranking


def calculate_dominance(target, h2h):
    rows = []

    for player in target:

        wins = 0
        rivals = 0

        for opponent in target:

            if player == opponent:
                continue

            s = h2h[player][opponent]

            total = (
                s["W"]
                + s["D"]
                + s["L"]
            )

            if total == 0:
                continue

            rivals += 1

            win_pct = (
                s["W"]
                / total
                * 100
            )

            if win_pct > 50:
                wins += 1

        rows.append((player, wins, rivals))

    return rows


def calculate_h2h_ranking(target, h2h):
    h2h_ranking = []

    for player in target:

        wins = 0
        matches = 0

        for rival in target:

            if player == rival:
                continue

            s = h2h[player][rival]

            wins += s["W"]

            matches += (
                s["W"]
                + s["D"]
                + s["L"]
            )

        if matches == 0:

            score = 0

        else:

            score = (
                wins
                / matches
                * 100
            )

        h2h_ranking.append(
            (
                player,
                score,
                matches,
                score * matches
            )
        )

    h2h_ranking.sort(
        key=lambda x: x[3],
        reverse=True
    )

    return h2h_ranking


def calculate_matchups(player, target, h2h, reverse):
    rows = []

    for rival in target:

        if rival == player:
            continue

        s = h2h[player][rival]

        total = s["W"] + s["D"] + s["L"]

        if total == 0:
            continue

        pct = s["W"] / total * 100

        rows.append((rival, pct, total))

    rows.sort(key=lambda x: x[1], reverse=reverse)

    return rows[:3]


def calculate_matchup_details(player, target, h2h, reverse):
    rows = []

    for rival in target:

        if rival == player:
            continue

        s = h2h[player][rival]

        total = s["W"] + s["D"] + s["L"]

        if total == 0:
            continue

        rows.append(matchup_record(rival, s))

    rows.sort(
        key=lambda x: x["win_pct"],
        reverse=reverse
    )

    return rows[:3]


def calculate_h2h_matrix(target, h2h):
    rows = []

    for player in sorted(target):

        rivals = []

        for rival in sorted(target):

            if player == rival:
                continue

            s = h2h[player][rival]

            total = s["W"] + s["D"] + s["L"]

            if total == 0:
                continue

            rivals.append(
                matchup_record(rival, s)
            )

        if not rivals:
            continue

        rows.append({
            "player": player,
            "rivals": rivals
        })

    return rows


def calculate_h2h_alerts(result):
    alerts = []

    for group in result["groups"]:

        for player_block in group["h2h_matrix"]:

            player = player_block["player"]

            for rival in player_block["rivals"]:

                if rival["win_pct"] < H2H_ALERT_THRESHOLD:
                    continue

                confidence = (
                    "HIGH"
                    if rival["matches"] >= MIN_H2H_ALERT_MATCHES
                    else "LOW SAMPLE"
                )

                signal = (
                    "STRONG"
                    if rival["win_pct"] >= 50
                    else "WATCH"
                )

                alerts.append({
                    "group_id": group["group_id"],
                    "group": group["label"],
                    "player": player,
                    "rival": rival["rival"],
                    "W": rival["W"],
                    "D": rival["D"],
                    "L": rival["L"],
                    "matches": rival["matches"],
                    "win_pct": rival["win_pct"],
                    "draw_pct": rival["draw_pct"],
                    "loss_pct": rival["loss_pct"],
                    "seq": rival.get("seq", ""),
                    "last5": rival.get("last5", ""),
                    "last10": rival.get("last10", ""),
                    "stk_win": rival.get("stk_win", 0),
                    "stk_lose": rival.get("stk_lose", 0),
                    "signal": signal,
                    "confidence": confidence,
                    "low_sample": rival["matches"] < MIN_H2H_ALERT_MATCHES
                })

    alerts.sort(
        key=lambda row: (
            row["confidence"] != "HIGH",
            -row["win_pct"],
            -row["matches"],
            row["player"],
            row["rival"]
        )
    )

    return alerts


def calculate_head_to_head(target, h2h):
    player_rows = []

    for p1 in sorted(target):

        rows = []

        for p2 in sorted(target):

            if p1 == p2:
                continue

            s = h2h[p1][p2]

            total = (
                s["W"]
                + s["D"]
                + s["L"]
            )

            if total == 0:
                continue

            win_pct = (
                s["W"] / total * 100
            )

            loss_pct = (
                s["L"] / total * 100
            )

            rows.append(
                (
                    p2,
                    win_pct,
                    loss_pct,
                    total
                )
            )

        if not rows:
            continue

        player_rows.append((p1, rows))

    return player_rows


def analyze_group(target_list, files):
    target = set(target_list)

    totals_5 = defaultdict(empty_record)
    totals_4 = defaultdict(empty_record)
    h2h = nested_h2h()

    count_5 = 0
    count_4 = 0

    for file in files:

        players = parse_vs_rivals(file)

        for player in target:

            if player not in players:
                continue

            for rival in target:

                if player == rival:
                    continue

                if rival not in players[player]:
                    continue

                add_record(
                    h2h[player][rival],
                    players[player][rival]
                )

        groups = build_groups(players)

        for group in groups:

            overlap = target & group

            if len(overlap) == 5:

                count_5 += 1

                overlap = list(overlap)

                for player in overlap:

                    for rival in overlap:

                        if player == rival:
                            continue

                        if rival not in players[player]:
                            continue

                        add_record(
                            totals_5[player],
                            players[player][rival]
                        )

            elif len(overlap) >= 4:

                count_4 += 1

                overlap = list(overlap)

                for player in overlap:

                    for rival in overlap:

                        if player == rival:
                            continue

                        if rival not in players[player]:
                            continue

                        add_record(
                            totals_4[player],
                            players[player][rival]
                        )

    h2h_keys = list(h2h.keys())
    target_repr = str(target)

    power_ranking = calculate_power_ranking(target, h2h)
    dominance = calculate_dominance(target, h2h)
    h2h_ranking = calculate_h2h_ranking(target, h2h)

    back_candidate = max(
        h2h_ranking,
        key=lambda x: x[1]
    )

    lay_candidate = min(
        h2h_ranking,
        key=lambda x: x[1]
    )

    return {
        "target_list": target_list,
        "group_id": "-".join(
            player.strip().lower()
            for player in target_list
        ),
        "label": " / ".join(target_list),
        "target_repr": target_repr,
        "h2h_keys": h2h_keys,
        "count_5": count_5,
        "count_4": count_4,
        "totals_5": totals_rows(totals_5),
        "totals_4": totals_rows(totals_4),
        "power_ranking": power_ranking,
        "dominance": dominance,
        "h2h_ranking": h2h_ranking,
        "back_candidate": back_candidate,
        "lay_candidate": lay_candidate,
        "back_matchups": calculate_matchups(
            back_candidate[0],
            target,
            h2h,
            True
        ),
        "back_matchup_details": calculate_matchup_details(
            back_candidate[0],
            target,
            h2h,
            True
        ),
        "lay_matchups": calculate_matchups(
            lay_candidate[0],
            target,
            h2h,
            False
        ),
        "lay_matchup_details": calculate_matchup_details(
            lay_candidate[0],
            target,
            h2h,
            False
        ),
        "head_to_head": calculate_head_to_head(target, h2h),
        "h2h_matrix": calculate_h2h_matrix(target, h2h)
    }


def analyze_league(league, groups):
    data_dir = data_dir_for(league)

    files = sorted(
        data_dir.glob("*player_stats.txt")
    )
    metadata = files_metadata(files)

    return {
        "league": league,
        "files_count": metadata["files_count"],
        "data_from": metadata["data_from"],
        "data_to": metadata["data_to"],
        "files": metadata["files"],
        "groups": [
            analyze_group(target_list, files)
            for target_list in groups[league]
        ]
    }


def render_header(result):
    print()
    print("=" * 80)
    print(result["league"])
    print("=" * 80)

    print(
        f"Analizando {result['files_count']} archivos..."
    )


def render_totals(rows):
    for row in rows:
        print(
            f"{row['player']:<12} "
            f"W={row['W']:>5} "
            f"D={row['D']:>5} "
            f"L={row['L']:>5} "
            f"WIN={row['win_pct']:6.2f}% "
            f"LOSS={row['loss_pct']:6.2f}%"
        )


def render_matchups(rows):
    for rival, pct, total in rows:

        print(f"   {rival:<12}{pct:6.2f}% ({total})")


def write_utf8_line(raw_prefix, value):
    sys.stdout.flush()
    sys.stdout.buffer.write(
        raw_prefix
        + value.encode("utf-8")
        + b"\n"
    )
    sys.stdout.flush()


def render_group(group):
    print()
    print("=" * 80)
    print("GROUP")
    print("=" * 80)
    print(", ".join(group["target_list"]))

    print()
    print("=" * 60)
    print("COINCIDENCIAS EXACTAS (5/5)")
    print("=" * 60)
    print(group["count_5"])

    print()

    render_totals(group["totals_5"])

    print()
    print("=" * 60)
    print("COINCIDENCIAS >= 4/5")
    print("=" * 60)
    print(group["count_4"])

    print()

    render_totals(group["totals_4"])

    print("TARGET:", group["target_repr"])
    print("H2H KEYS:", group["h2h_keys"])

    print()
    print("=" * 60)
    print("POWER RANKING")
    print("=" * 60)

    for pos, (player, score) in enumerate(
        group["power_ranking"],
        start=1
    ):

        print(
            f"{pos}. "
            f"{player:<12} "
            f"{score:7.2f}"
        )

    print()
    print("=" * 60)
    print("DOMINANCE")
    print("=" * 60)

    for player, wins, rivals in group["dominance"]:
        print(
            f"{player:<12} "
            f"{wins}/{rivals}"
        )

    print()
    print("=" * 60)
    print("H2H RANKING")
    print("=" * 60)

    for player, score, matches, _ in group["h2h_ranking"]:

        print(
            f"{player:<12} "
            f"{score:6.2f}% "
            f"({matches} matches)"
        )

    print()
    print("=" * 60)
    print("BETTING CANDIDATE")
    print("=" * 60)

    back_candidate = group["back_candidate"]
    lay_candidate = group["lay_candidate"]

    print()
    print("=" * 60)
    print("BETTING SUGGESTION")
    print("=" * 60)

    print()
    write_utf8_line(
        b"\xf0\x9f\x8f\x86 BACK : ",
        back_candidate[0]
    )
    print(f"H2H Score : {back_candidate[1]:.2f}%")
    print("Best matchups:")
    render_matchups(group["back_matchups"])

    print()
    write_utf8_line(
        b"\xf0\x9f\x92\x80 LAY : ",
        lay_candidate[0]
    )
    print(f"H2H Score : {lay_candidate[1]:.2f}%")
    print("Worst matchups:")
    render_matchups(group["lay_matchups"])

    print()
    print("=" * 60)
    print("HEAD TO HEAD")
    print("=" * 60)

    for p1, rows in group["head_to_head"]:

        print()
        print(p1)

        for rival, win_pct, loss_pct, total in rows:

            print(
                f"{rival:<12} "
                f"W={win_pct:6.2f}% "
                f"L={loss_pct:6.2f}% "
                f"({total})"
            )


def render_result(result):
    render_header(result)

    for group in result["groups"]:
        render_group(group)


def json_ready_group(group):
    return {
        "group_id": group["group_id"],
        "label": group["label"],
        "target": group["target_list"],
        "target_repr": group["target_repr"],
        "h2h_keys": group["h2h_keys"],
        "coincidencias_5": group["count_5"],
        "coincidencias_4": group["count_4"],
        "totals_5": group["totals_5"],
        "totals_4": group["totals_4"],
        "power_ranking": [
            {
                "position": pos,
                "player": player,
                "score": score
            }
            for pos, (player, score) in enumerate(
                group["power_ranking"],
                start=1
            )
        ],
        "dominance": [
            {
                "player": player,
                "wins": wins,
                "rivals": rivals
            }
            for player, wins, rivals in group["dominance"]
        ],
        "h2h_ranking": [
            {
                "player": player,
                "score": score,
                "matches": matches,
                "weighted_score": weighted_score
            }
            for player, score, matches, weighted_score
            in group["h2h_ranking"]
        ],
        "betting": {
            "back": {
                "player": group["back_candidate"][0],
                "score": group["back_candidate"][1],
                "matches": group["back_candidate"][2],
                "weighted_score": group["back_candidate"][3],
                "best_matchups": [
                    {
                        "rival": rival,
                        "win_pct": pct,
                        "matches": total
                    }
                    for rival, pct, total in group["back_matchups"]
                ],
                "best_matchup_details":
                    group["back_matchup_details"]
            },
            "lay": {
                "player": group["lay_candidate"][0],
                "score": group["lay_candidate"][1],
                "matches": group["lay_candidate"][2],
                "weighted_score": group["lay_candidate"][3],
                "worst_matchups": [
                    {
                        "rival": rival,
                        "win_pct": pct,
                        "matches": total
                    }
                    for rival, pct, total in group["lay_matchups"]
                ],
                "worst_matchup_details":
                    group["lay_matchup_details"]
            }
        },
        "head_to_head": [
            {
                "player": player,
                "rivals": [
                    {
                        "rival": rival,
                        "win_pct": win_pct,
                        "loss_pct": loss_pct,
                        "matches": total
                    }
                    for rival, win_pct, loss_pct, total in rows
                ]
            }
            for player, rows in group["head_to_head"]
        ],
        "h2h_matrix": group["h2h_matrix"]
    }


def json_ready_league(result):
    return {
        "league": result["league"],
        "files_count": result["files_count"],
        "data_from": result["data_from"],
        "data_to": result["data_to"],
        "files": result["files"],
        "h2h_alert_threshold": H2H_ALERT_THRESHOLD,
        "min_h2h_alert_matches": MIN_H2H_ALERT_MATCHES,
        "h2h_alerts": calculate_h2h_alerts(result),
        "groups": [
            json_ready_group(group)
            for group in result["groups"]
        ]
    }


def write_json(result, all_results):
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(
            ZoneInfo("Europe/Madrid")
        ).strftime("%d/%m/%Y %H:%M:%S %Z"),
        "league": result["league"],
        "files_count": result["files_count"],
        "data_from": result["data_from"],
        "data_to": result["data_to"],
        "files": result["files"],
        "h2h_alert_threshold": H2H_ALERT_THRESHOLD,
        "min_h2h_alert_matches": MIN_H2H_ALERT_MATCHES,
        "h2h_alerts": calculate_h2h_alerts(result),
        "groups": [
            json_ready_group(group)
            for group in result["groups"]
        ],
        "leagues": {
            league: json_ready_league(league_result)
            for league, league_result in all_results.items()
        }
    }

    with open(
        JSON_OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2
        )


def main():
    groups = load_groups()

    if len(sys.argv) < 2:
        print("Uso: python group_analysis.py [GT|EADRIATIC]")
        sys.exit(1)

    league = sys.argv[1].upper()

    if league == "ALL":
        selected_leagues = ["GT", "EADRIATIC"]
    else:
        selected_leagues = [league]

    all_results = {
        item: analyze_league(item, groups)
        for item in ["GT", "EADRIATIC"]
    }

    result = all_results[selected_leagues[0]]

    write_json(result, all_results)

    for item in selected_leagues:
        render_result(all_results[item])


if __name__ == "__main__":
    main()
