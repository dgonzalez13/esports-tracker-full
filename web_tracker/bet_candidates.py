"""Candidate formatting; no bets are placed by this module."""
from datetime import datetime
from zoneinfo import ZoneInfo


def candidate(rival, horizon):
    total = rival.get('historical_played', 0)
    wins = rival.get('historical_wins', 0)
    losses = rival.get('historical_losses', 0)
    recent = rival.get('last20', {})
    sequence = rival.get('current_pair_sequence', rival.get('sequence', ''))
    if (not total or wins * 100 <= 37 * total or wins <= losses
            or recent.get('available') != 20 or recent.get('gap', 0) <= 0
            or 'V' in sequence or len(sequence) >= horizon):
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
