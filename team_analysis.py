"""Directional player/team statistics from explicitly observed teams."""
from current_streaks_v2 import _record_time
from match_history import clean_name, name_key


def gt_team(participant):
    team = participant.get('participant', {}).get('team') or {}
    if not isinstance(team, dict):
        return None, None
    name = team.get('name')
    return (clean_name(name) if isinstance(name, str) and name.strip() else None, team.get('id'))


def calculate_team_stats(records, reference_time):
    groups = {}
    seen = set()
    for record in records:
        stamp = _record_time(record)
        if stamp is None or stamp > reference_time or record.get('result') not in {'V', 'E', 'D'}:
            continue
        player_team, rival_team = record.get('player_team'), record.get('rival_team')
        if not isinstance(player_team, str) or not player_team.strip() or not isinstance(rival_team, str) or not rival_team.strip():
            continue
        identity = (record['league'], record.get('match_id'), record['player_key'])
        if identity in seen:
            continue
        seen.add(identity)
        # Use source team IDs where available, with names as fallback.
        key = (record['league'], record['player_key'], record['rival_key'],
               str(record.get('player_team_id') or name_key(player_team)),
               str(record.get('rival_team_id') or name_key(rival_team)))
        row = groups.setdefault(key, dict(league=record['league'], player=record['player'], rival=record['rival'],
                                         player_team=player_team, rival_team=rival_team,
                                         played=0, wins=0, draws=0, losses=0))
        row['played'] += 1
        row[{'V': 'wins', 'E': 'draws', 'D': 'losses'}[record['result']]] += 1
    for row in groups.values():
        for result in ('wins', 'draws', 'losses'):
            row[result + '_pct'] = row[result] / row['played'] * 100
    return sorted(groups.values(), key=lambda r: (-r['played'], r['league'], r['player'], r['rival'], r['player_team'], r['rival_team']))
