"""Candidate formatting; no bets are placed by this module."""
from datetime import datetime
from zoneinfo import ZoneInfo


def six_sample_allowed(rival):
    stats = rival.get('pair_stats', {})
    sample = stats.get('complete_series', 0)
    failures = stats.get('zero_win_series')
    return (sample >= 8 and failures is not None and 0 <= failures <= sample
            and failures * 100 <= 5 * sample)


def six_rating(rival):
    total = rival.get('historical_played', 0)
    wins = rival.get('historical_wins', 0)
    losses = rival.get('historical_losses', 0)
    stats = rival.get('pair_stats', {})
    sample = stats.get('complete_series', 0)
    failures = stats.get('zero_win_series')
    if (not total or wins * 100 <= 30 * total or (wins-losses)*100 < -10*total
            or not six_sample_allowed(rival)):
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


def first_victory_sample(rival, horizon):
    played = len(rival.get('current_pair_sequence', rival.get('sequence', '')))
    return next((row for row in rival.get('pair_stats', {}).get('pair_horizons', [])
                 if row['initial_without_win'] == played and row['horizon'] == horizon), {})


def missing_schedule_text(rival):
    message = 'Sin calendario: comprobar horarios y resultados manualmente'
    inferred = rival.get('inferred_pair')
    if inferred:
        message += (f' [Registrados: {inferred["observed"]}; '
                    f'posibles pendientes hasta 6: {inferred["possible_remaining"]}]')
    return message


def candidate(rival, horizon, league=None):
    sequence = rival.get('current_pair_sequence', rival.get('sequence', ''))
    effective_total = max(0, 6 - rival.get('pair_cancelled', 0))
    target = min(horizon, effective_total)
    original_horizon = first_victory_horizon(rival)
    small_sample = (original_horizon is not None
                    and first_victory_sample(rival, original_horizon).get('sample', 0) < 10)
    if horizon == 6:
        if not six_sample_allowed(rival):
            return None
        if not small_sample and six_rating(rival) is None:
            return None
    elif horizon in (4, 5) and (original_horizon != horizon or small_sample):
        return None
    if 'V' in sequence or len(sequence) >= target:
        return None
    fixtures = rival.get('pair_fixtures', [])[:target - len(sequence)]
    if not fixtures and league != "EADRIATIC":
        return None
    number = len(sequence) + 1
    stake = {4: 10, 5: 5, 6: 3}[horizon] * 2 ** (number - 1)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    schedule_text = ' --- '.join(hours) if fixtures else missing_schedule_text(rival)
    line = f'[{number}] {stake} ' + schedule_text
    if horizon in (4, 5):
        row = first_victory_sample(rival, horizon)
        line += f' [{row["win_pct"]:.2f}% (n={row["sample"]})]'
    if rival.get('pair_cancelled'):
        line += f' [{rival["pair_cancelled"]} cancelado(s); máximo {effective_total} partidos efectivos]'
    if fixtures and fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    missing = target - len(sequence) - len(fixtures)
    if missing and fixtures:
        line += f' --- Faltan {missing} horarios por publicar'
    if horizon == 6:
        stats = rival['pair_stats']
        sample = stats['complete_series']
        line += f' [n={sample}; Sin V={stats["zero_win_series"] * 100 / sample:.2f}%]'
    return fixtures[0]['timestamp'] if fixtures else '9999', line


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


def first_win_window_candidate(rival, league, minimum_sample=10):
    sequence = rival.get('current_pair_sequence', rival.get('sequence', ''))
    if sequence.count('V') != 1:
        return None
    first, played = sequence.index('V')+1, len(sequence)
    rows = rival.get('pair_stats', {}).get('first_win_followups', [])
    if sequence.endswith('V'):
        consecutive = next((r for r in rows if r['league'] == league
                            and r['first_win_position'] == first and r['window'] == 1), None)
        if (not consecutive or not consecutive.get('sample') or consecutive.get('win_pct') is None
                or consecutive['win_pct'] <= 50):
            return None
    effective_total = max(0, 6-rival.get('pair_cancelled', 0))
    targets = []
    for row in rows:
        if (row['league'] != league or row['first_win_position'] != first
                or row.get('win_pct') is None or row['win_pct'] <= 90 or not row.get('sample')):
            continue
        window = row['window']
        if window not in (1, 3, 4, 5, 0) or (window == 0 and first not in (4, 5)):
            continue
        deadline = 6 if window == 0 else first+window
        if played < deadline <= min(6, effective_total) and deadline-played <= 5:
            targets.append((deadline, row))
    if not targets:
        return None
    deadline, row = min(targets, key=lambda item: item[0])
    if row['sample'] < minimum_sample:
        return None
    remaining = deadline-played
    fixtures = rival.get('pair_fixtures', [])[:remaining]
    if not fixtures and league != "EADRIATIC":
        return None
    stake = 80 // 2**(remaining-1)
    hours = [datetime.fromisoformat(f['timestamp']).astimezone(ZoneInfo('Europe/Madrid'))
             .strftime('%H:%M') for f in fixtures]
    schedule_text = ' --- '.join(hours) if fixtures else missing_schedule_text(rival)
    line = f'[{played+1}] {stake} ' + schedule_text
    line += f' [Hasta partido {deadline}: {row["win_pct"]:.2f}% (n={row["sample"]})]'
    if fixtures and fixtures[0].get('started'):
        line += ' [Iniciado: pendiente de resultado; número provisional]'
    if fixtures and len(fixtures) < remaining:
        line += f' [Faltan {remaining-len(fixtures)} horarios por publicar]'
    return fixtures[0]['timestamp'] if fixtures else '9999', line
