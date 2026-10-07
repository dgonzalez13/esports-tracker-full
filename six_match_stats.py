"""Leakage-free empirical frequencies for inferred six-match sessions."""
from collections import defaultdict
from datetime import timedelta

from current_streaks_v2 import _record_time, split_player_sessions

GAP_LABELS = ("A por detrás (< −5 pp)", "Equilibrados (−5 a +5 pp)",
              "Ventaja de A (>5 a 15 pp)", "Ventaja amplia de A (>15 pp)")
REPEAT_BANDS = (">40%", "35–40% (incluidos)", "30–<35%")
REPEAT_CONDITIONS = ("Victoria en el primer partido", "Victoria en el segundo partido",
                     "Primera victoria en el segundo partido")


def gap_band(wins, losses, played):
    # Compare counts before dividing, avoiding floating-point boundary drift.
    difference = (wins - losses) * 100
    return 0 if difference < -5 * played else 1 if difference <= 5 * played else 2 if difference <= 15 * played else 3


def calculate_six_match_stats(records, reference_time, minimum_prior=20):
    players = defaultdict(list)
    seen = set()
    for row in records:
        stamp = _record_time(row)
        if stamp is None or stamp > reference_time or row.get("result") not in {"V", "E", "D"}:
            continue
        key = (row.get("league"), row.get("player_key"), row.get("match_id") or stamp,
               row.get("rival_key"))
        if key in seen:
            continue
        seen.add(key)
        players[key[:2]].append(row)
    counts = defaultdict(lambda: [[0, 0] for _ in range(6)])
    horizons = defaultdict(lambda: [0, 0])
    gap_counts = defaultdict(lambda: [[0, 0] for _ in range(6)])
    gap_horizons = defaultdict(lambda: [0, 0])
    conditional_horizons = defaultdict(lambda: [0, 0])
    repeat_counts = defaultdict(lambda: [0, 0, 0, 0, 0])
    complete = 0
    for (league, player), history in players.items():
        prior = defaultdict(list)
        for session in split_player_sessions(history):
            pairs = defaultdict(list)
            for row in session:
                pairs[row["rival_key"]].append(row)
            closed = _record_time(session[-1]) + timedelta(minutes=90) < reference_time
            for rival, matches in pairs.items():
                earlier = prior[rival]
                if len(matches) == 6 and closed:
                    complete += 1
                    if len(earlier) >= minimum_prior:
                        wins = sum(r["result"] == "V" for r in earlier)
                        losses = sum(r["result"] == "D" for r in earlier)
                        pct = wins / len(earlier) * 100
                        band = gap_band(wins, losses, len(earlier))
                        sequence = ''.join(r["result"] for r in matches)
                        repeat_band = 0 if pct > 40 else 1 if pct >= 35 else 2 if pct >= 30 else None
                        if repeat_band is not None:
                            for condition, position, eligible in (
                                (0, 1, sequence[0] == 'V'),
                                (1, 2, sequence[1] == 'V'),
                                (2, 2, sequence[0] != 'V' and sequence[1] == 'V'),
                            ):
                                if eligible:
                                    sample = repeat_counts[(league, repeat_band, condition)]
                                    sample[0] += 1
                                    sample[1] += sequence[position] == 'V'
                                    for index, horizon in enumerate((4, 5, 6), 2):
                                        sample[index] += 'V' in sequence[position:horizon]
                        for threshold in (35, 40):
                            if pct <= threshold:
                                continue
                            for horizon in (4, 5, 6):
                                sample = horizons[(league, threshold, horizon)]
                                sample[0] += 1
                                sample[1] += "V" in sequence[:horizon]
                                sample = gap_horizons[(league, threshold, band, horizon)]
                                sample[0] += 1
                                sample[1] += "V" in sequence[:horizon]
                            for k in range(6):
                                if "V" not in sequence[:k]:
                                    for horizon in (4, 5, 6):
                                        if k < horizon:
                                            sample = conditional_horizons[(league, threshold, band, k, horizon)]
                                            sample[0] += 1
                                            sample[1] += "V" in sequence[k:horizon]
                                    sample = counts[(league, threshold)][k]
                                    sample[0] += 1
                                    sample[1] += "V" not in sequence
                                    sample = gap_counts[(league, threshold, band)][k]
                                    sample[0] += 1
                                    sample[1] += "V" not in sequence
                prior[rival].extend(matches)
    return {"minimum_prior": minimum_prior, "complete_series": complete,
            "repeat_rows": [
                {"league": league, "band": label, "condition": label_condition,
                 "sample": counts[0], "next_win_pct": counts[1] / counts[0] * 100 if counts[0] else None,
                 "repeat_by_4_pct": counts[2] / counts[0] * 100 if counts[0] else None,
                 "repeat_by_5_pct": counts[3] / counts[0] * 100 if counts[0] else None,
                 "repeat_by_6_pct": counts[4] / counts[0] * 100 if counts[0] else None,
                 "repeat_by_6": counts[4]}
                for league in sorted({key[0] for key in players})
                for band, label in enumerate(REPEAT_BANDS)
                for condition, label_condition in enumerate(REPEAT_CONDITIONS)
                for counts in [repeat_counts[(league, band, condition)]]
            ],
            "conditional_horizons": [
                {"league": league, "threshold": threshold, "band": label,
                 "initial_without_win": k, "horizon": horizon, "sample": sample,
                 "win_pct": wins / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players}) for threshold in (35, 40)
                for band, label in enumerate(GAP_LABELS) for horizon in (4, 5, 6) for k in range(horizon)
                for sample, wins in [conditional_horizons[(league, threshold, band, k, horizon)]]
            ],
            "gap_horizons": [
                {"league": league, "threshold": threshold, "band": label, "horizon": horizon,
                 "sample": sample, "with_win": wins,
                 "win_pct": wins / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players}) for threshold in (35, 40)
                for band, label in enumerate(GAP_LABELS) for horizon in (4, 5, 6)
                for sample, wins in [gap_horizons[(league, threshold, band, horizon)]]
            ],
            "gap_rows": [
                {"league": league, "threshold": threshold, "band": label, "initial_without_win": k,
                 "sample": sample, "zero_wins": zero,
                 "zero_win_pct": zero / sample * 100 if sample else None,
                 "remaining_win_pct": (sample - zero) / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players}) for threshold in (35, 40)
                for band, label in enumerate(GAP_LABELS)
                for k, (sample, zero) in enumerate(gap_counts[(league, threshold, band)])
            ],
            "horizons": [
                {"league": league, "threshold": threshold, "horizon": horizon,
                 "sample": sample, "with_win": wins,
                 "win_pct": wins / sample * 100 if sample else None,
                 "without_win_pct": (sample - wins) / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players})
                for threshold in (35, 40) for horizon in (4, 5, 6)
                for sample, wins in [horizons[(league, threshold, horizon)]]
            ],
            "rows": [
                {"league": league, "threshold": threshold, "initial_without_win": k,
                 "sample": sample, "zero_wins": zero,
                 "zero_win_pct": zero / sample * 100 if sample else None,
                 "remaining_win_pct": (sample - zero) / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players})
                for threshold in (35, 40)
                for k, (sample, zero) in enumerate(counts[(league, threshold)])
            ]}
