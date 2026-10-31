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
    if horizon == 6:
        if six_rating(rival) is None:
            return None
    elif (not total or wins * 100 <= 37 * total or wins <= losses
            or recent.get('available') != 20 or recent.get('gap', 0) <= 0
            ):
        return None
    if 'V' in sequence or len(sequence) >= horizon:
        return None
    fixtures = rival.get('pair_fixtures', [])[:horizon - len(sequence)]
    # A pending result prevents knowing which numbered future match comes next.
    if not fixtures or fixtures[0].get('started'):
        return None
    number = len(sequence) + 1
    stake = (10 if horizon == 4 else 3) * 2 ** (number - 1)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%d/%m %H:%M') for f in fixtures]
    line = f'[{number}] {stake} ' + ' --- '.join(hours)
    missing = horizon - len(sequence) - len(fixtures)
    if missing:
        line += f' --- Faltan {missing} horarios por publicar'
    return fixtures[0]['timestamp'], line
