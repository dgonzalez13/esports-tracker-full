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


def candidate(rival, horizon):
    total = rival.get('historical_played', 0)
    wins = rival.get('historical_wins', 0)
    losses = rival.get('historical_losses', 0)
    recent = rival.get('last20', {})
    sequence = rival.get('current_pair_sequence', rival.get('sequence', ''))
    effective_total = max(0, 6 - rival.get('pair_cancelled', 0))
    target = min(horizon, effective_total)
    if horizon == 6:
        if six_rating(rival) is None:
            return None
    elif (not total or wins * 100 <= 37 * total or wins <= losses
            or (recent.get('available') == 20 and recent.get('gap', 0) <= 0)
            ):
        return None
    if 'V' in sequence or len(sequence) >= target:
        return None
    fixtures = rival.get('pair_fixtures', [])[:target - len(sequence)]
    if not fixtures:
        return None
    number = len(sequence) + 1
    stake = (10 if horizon == 4 else 3) * 2 ** (number - 1)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    line = f'[{number}] {stake} ' + ' --- '.join(hours)
    if rival.get('pair_cancelled'):
        line += f' [{rival["pair_cancelled"]} cancelado(s); máximo {effective_total} partidos efectivos]'
    if fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    if horizon == 4 and recent.get('available') != 20:
        line += ' [Sin Dif.20: histórico detallado insuficiente]'
    missing = target - len(sequence) - len(fixtures)
    if missing:
        line += f' --- Faltan {missing} horarios por publicar'
    return fixtures[0]['timestamp'], line


def repeat_candidate(rival, league, minimum_prior=20, initial_stake=20):
    """Three remaining games, using the percentages displayed in Repeat Victory."""
    sequence = rival.get('sequence', '')
    if len(sequence) != 3 or sequence.count('V') != 1 or sequence.index('V') not in (0, 1):
        return None
    prior = rival.get('historical_played', 0) - 3
    wins = rival.get('historical_wins', 0) - 1
    recent = rival.get('prior20', {})
    if prior < minimum_prior or wins < 0 or recent.get('available') != 20 or recent.get('win_pct') is None:
        return None
    pct, pct20 = wins*100/prior, recent['win_pct']
    if pct < 30 or (pct+pct20)/2 <= 40:
        return None
    position = sequence.index('V') + 1
    sample = next((r for r in rival.get('pair_stats', {}).get('pair_repeat_rows', [])
                   if r['league'] == league and r['win_position'] == position and r['played'] == 3), None)
    pct6 = sample.get('repeat_by_6_pct') if sample else None
    if (pct6 is None or pct6 < 85
            or sample.get('repeat_by_6_sample', sample.get('sample', 0)) <= 0):
        return None
    total = max(0, 6-rival.get('pair_cancelled', 0))
    remaining = max(0, total-3)
    fixtures = rival.get('pair_fixtures', [])[:remaining]
    if not fixtures:
        return None
    stars = int(pct < 40 or pct20 < 40) + int(85 <= pct6 <= 90)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    line = f'[4] {initial_stake} ' + ' --- '.join(hours)
    if fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    if remaining < 3:
        line += f' [Solo {remaining} partidos efectivos pendientes por cancelación]'
    if len(fixtures) < remaining:
        line += f' [Faltan {remaining-len(fixtures)} horarios por publicar]'
    return fixtures[0]['timestamp'], '*'*stars, line
