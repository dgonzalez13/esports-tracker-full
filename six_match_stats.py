"""Leakage-free empirical frequencies for inferred six-match sessions."""
from collections import defaultdict
from datetime import timedelta

from current_streaks_v2 import _record_time, split_player_sessions


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
                        pct = sum(r["result"] == "V" for r in earlier) / len(earlier) * 100
                        sequence = ''.join(r["result"] for r in matches)
                        for threshold in (35, 40):
                            if pct <= threshold:
                                continue
                            for k in range(6):
                                if "V" not in sequence[:k]:
                                    sample = counts[(league, threshold)][k]
                                    sample[0] += 1
                                    sample[1] += "V" not in sequence
                prior[rival].extend(matches)
    return {"minimum_prior": minimum_prior, "complete_series": complete,
            "rows": [
                {"league": league, "threshold": threshold, "initial_without_win": k,
                 "sample": sample, "zero_wins": zero,
                 "zero_win_pct": zero / sample * 100 if sample else None,
                 "remaining_win_pct": (sample - zero) / sample * 100 if sample else None}
                for league in sorted({key[0] for key in players})
                for threshold in (35, 40)
                for k, (sample, zero) in enumerate(counts[(league, threshold)])
            ]}
