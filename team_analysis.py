"""Unique physical matches with explicitly observed player and team identities."""
from current_streaks_v2 import _record_time
from match_history import clean_name, name_key


def canonical_team_name(value):
    """Unify known source abbreviations; never guess unfamiliar club names."""
    import re
    import unicodedata
    token = re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())
    families = {
        'Barcelona': ('barcelona', 'fcbarcelona'),
        'Bayern Munich': ('bayern', 'bayernm', 'bayernmunich', 'fcbayernmunich', 'bayernmunchen', 'fcbayernmunchen'),
        'Atletico Madrid': ('amadrid', 'atleticom', 'atleticomadrid', 'atleticodemadrid'),
        'Athletic Bilbao': ('abilbao', 'athleticbilbao', 'atleticbilbao', 'athleticclub'),
        'Manchester City': ('mancity', 'manchestercity', 'manchestercityfc'),
        'Manchester United': ('manutd', 'manunited', 'manchesterunited', 'manchesterunitedfc'),
        'PSG': ('psg', 'parissg', 'parissaintgermain', 'parisstgermain'),
        'Real Madrid': ('realmadrid', 'realmadridcf'),
    }
    return next((name for name, aliases in families.items() if token in aliases), clean_name(value))


def gt_team(participant):
    team = participant.get('participant', {}).get('team') or {}
    if not isinstance(team, dict):
        return None, None
    name = team.get('name')
    return (clean_name(name) if isinstance(name, str) and name.strip() else None, team.get('id'))


def calculate_team_stats(records, reference_time):
    """One physical match per row; the viewer selects the player perspective."""
    from collections import defaultdict
    from zoneinfo import ZoneInfo

    eligible = []
    team_ids = defaultdict(set)
    for row in records:
        stamp = _record_time(row)
        if stamp is None or stamp > reference_time or row.get('result') not in {'V', 'E', 'D'}:
            continue
        fields = ('player', 'rival', 'player_team', 'rival_team')
        if any(not isinstance(row.get(f), str) or not row[f].strip() for f in fields):
            continue
        eligible.append((stamp, row))
        for prefix in ('player', 'rival'):
            identity = row.get(prefix + '_team_id')
            if identity is not None:
                team_ids[(row['league'], name_key(canonical_team_name(row[prefix + '_team'])))].add(str(identity))

    players, teams, matches = [], [], []
    player_index, team_index = {}, {}
    seen_ids, seen_physical = set(), set()

    def player_id(league, name):
        key = league, name_key(name)
        if key not in player_index:
            player_index[key] = len(players)
            players.append(dict(name=clean_name(name), league=league))
        return player_index[key]

    def team_id(league, name, native):
        name = canonical_team_name(name)
        known = team_ids[(league, name_key(name))]
        if native is None and len(known) == 1:
            native = next(iter(known))
        key = (league, 'id', str(native)) if native is not None else (league, 'name', name_key(name))
        if key not in team_index:
            team_index[key] = len(teams)
            teams.append(dict(name=clean_name(name), league=league))
        return team_index[key]

    for stamp, row in sorted(eligible, key=lambda item: (item[0], str(item[1].get('match_id', '')))):
        league = row['league']
        physical = (league, stamp, tuple(sorted((name_key(row['player']), name_key(row['rival'])))))
        identity = (league, row.get('match_id')) if row.get('match_id') else physical
        if identity in seen_ids or physical in seen_physical:
            continue
        seen_ids.add(identity)
        seen_physical.add(physical)
        sides = [(row['player'], row['player_team'], row.get('player_team_id')),
                 (row['rival'], row['rival_team'], row.get('rival_team_id'))]
        result = row['result']
        if name_key(sides[0][0]) > name_key(sides[1][0]):
            sides.reverse()
            result = {'V': 'D', 'E': 'E', 'D': 'V'}[result]
        a, b = sides
        matches.append([league, stamp.astimezone(ZoneInfo('Europe/Madrid')).date().isoformat(),
                        player_id(league, a[0]), team_id(league, a[1], a[2]),
                        player_id(league, b[0]), team_id(league, b[1], b[2]), result])
    dates = [row[1] for row in matches]
    return dict(schema_version=1, players=players, teams=teams, matches=matches,
                unique_matches=len(matches), first_date=min(dates) if dates else None,
                last_date=max(dates) if dates else None)
