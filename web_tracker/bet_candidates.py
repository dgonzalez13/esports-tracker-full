"""Candidate formatting; no bets are placed by this module."""
from datetime import datetime
from zoneinfo import ZoneInfo


def six_rating(rival):
    total = rival.get('historical_played', 0)
    wins = rival.get('historical_wins', 0)
    losses = rival.get('historical_losses', 0)
    stats = rival.get('pair_stats', {})
    sample = stats.get('complete_series', 0)
    failures = stats.get('zero_win_series')
    if (not total or wins * 100 <= 30 * total or (wins-losses)*100 < -10*total
            or sample < 8 or failures is None or not 0 <= failures <= sample
            or failures * 100 > 10 * sample):
        return None
    level = 1 if wins > losses else 2 if (wins-losses)*100 >= -5*total else 3
    warnings = []
    if sample in (8, 9):
        warnings.append(f'Solo {sample} series de 6')
    if failures * 100 >= 5 * sample:
        warnings.append(f'Sin V: {failures * 100 / sample:.2f}%')
    return level, warnings


def first_victory_horizon(rival):
    total = rival.get('historical_played', 0)
    recent = rival.get('last20', {})
    if not total or recent.get('available') != 20 or recent.get('win_pct') is None:
        return None
    pct = rival.get('historical_wins', 0)*100/total
    pct20 = recent['win_pct']
    if pct < 35 or pct20 < 35 or (pct+pct20)/2 < 40:
        return None
    played = len(rival.get('current_pair_sequence', rival.get('sequence', '')))
    rows = rival.get('pair_stats', {}).get('pair_horizons', [])
    def probability(horizon):
        row = next((r for r in rows if r['initial_without_win'] == played and r['horizon'] == horizon), None)
        return row.get('win_pct') if row and row.get('sample', 0) > 0 and played < horizon else None
    four = probability(4)
    if four is not None and four >= 90:
        return 4
    five = probability(5)
    return 5 if five is not None and five >= 90 else None


def candidate(rival, horizon):
    sequence = rival.get('current_pair_sequence', rival.get('sequence', ''))
    effective_total = max(0, 6 - rival.get('pair_cancelled', 0))
    target = min(horizon, effective_total)
    if horizon == 6:
        if six_rating(rival) is None:
            return None
    elif horizon in (4, 5) and first_victory_horizon(rival) != horizon:
        return None
    if 'V' in sequence or len(sequence) >= target:
        return None
    fixtures = rival.get('pair_fixtures', [])[:target - len(sequence)]
    if not fixtures:
        return None
    number = len(sequence) + 1
    stake = (10 if horizon in (4, 5) else 3) * 2 ** (number - 1)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    line = f'[{number}] {stake} ' + ' --- '.join(hours)
    if rival.get('pair_cancelled'):
        line += f' [{rival["pair_cancelled"]} cancelado(s); máximo {effective_total} partidos efectivos]'
    if fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    missing = target - len(sequence) - len(fixtures)
    if missing:
        line += f' --- Faltan {missing} horarios por publicar'
    return fixtures[0]['timestamp'], line


def repeat_candidate(rival, league, minimum_prior=20, initial_stake=20):
    """Up to three remaining games, using the percentages in Repeat Victory."""
    sequence = rival.get('sequence', '')
    played = len(sequence)
    if not 3 <= played < 6 or sequence.count('V') != 1 or sequence.index('V') not in (0, 1):
        return None
    prior = rival.get('historical_played', 0) - played
    wins = rival.get('historical_wins', 0) - 1
    recent = rival.get('prior20', {})
    if prior < minimum_prior or wins < 0 or recent.get('available') != 20 or recent.get('win_pct') is None:
        return None
    pct, pct20 = wins*100/prior, recent['win_pct']
    if pct < 30 or (pct+pct20)/2 <= 40:
        return None
    position = sequence.index('V') + 1
    sample = next((r for r in rival.get('pair_stats', {}).get('pair_repeat_rows', [])
                   if r['league'] == league and r['win_position'] == position and r['played'] == played), None)
    pct6 = sample.get('repeat_by_6_pct') if sample else None
    if (pct6 is None or pct6 < 85
            or sample.get('repeat_by_6_sample', sample.get('sample', 0)) <= 0):
        return None
    total = max(0, 6-rival.get('pair_cancelled', 0))
    remaining = max(0, total-played)
    fixtures = rival.get('pair_fixtures', [])[:remaining]
    if not fixtures:
        return None
    stars = int(pct < 40 or pct20 < 40) + int(85 <= pct6 <= 90)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    stake = initial_stake * 2 ** (played-3)
    line = f'[{played+1}] {stake} ' + ' --- '.join(hours)
    if fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    if rival.get('pair_cancelled'):
        line += f' [Solo {remaining} partidos efectivos pendientes por cancelación]'
    if len(fixtures) < remaining:
        line += f' [Faltan {remaining-len(fixtures)} horarios por publicar]'
    return fixtures[0]['timestamp'], '*'*stars, line
