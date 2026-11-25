"""Apply Current Streaks indicators consistently to visible player names."""

import re

from bs4 import BeautifulSoup, Comment

from match_history import name_key


MARKERS = {'GREEN': '\U0001f7e2', 'RED': '\U0001f534'}


def decorate_player_names(html, payload):
    players = {}
    names = set()
    for league, rows in (payload or {}).get('leagues', {}).items():
        for row in rows:
            name = str(row.get('player') or '').strip()
            if not name:
                continue
            names.add(name)
            players.setdefault(name_key(name), {})[league] = MARKERS.get(
                row.get('indicator'), row.get('balance', '') if not row.get('indicator') else '')
    if not names:
        return html
    # Longest names first; never match a player inside another word/name.
    pattern = re.compile(r'(?<![\w])(?:[\U0001f7e2\U0001f534]\s*)?('
                         + '|'.join(re.escape(name) for name in sorted(names, key=len, reverse=True))
                         + r')(?![\w])', re.IGNORECASE)
    soup = BeautifulSoup(html, 'html.parser')
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment) or any(parent.name in {'script', 'style', 'head'} for parent in node.parents):
            continue
        if not pattern.search(str(node)):
            continue
        league = None
        for parent in node.parents:
            if parent.get('data-league'):
                league = parent['data-league']
                break
            # Tables identify the league in a cell; text candidates start with it.
            context = str(node) if parent.name not in {'tr', 'article'} else parent.get_text(' ')
            leagues = set(re.findall(r'\b(GT|EADRIATIC)\b', context, re.IGNORECASE))
            if len(leagues) == 1:
                league = leagues.pop().upper()
                break

        def replace(match):
            name = match.group(1)
            options = players[name_key(name)]
            if league is not None:
                marker = options.get(league, '')
            elif len(set(options.values())) == 1:
                marker = next(iter(options.values()))
            else:
                # A shared name with different league indicators needs context.
                return match.group(0)
            return f'{marker} {name}' if marker else name

        node.replace_with(pattern.sub(replace, str(node)))
    return str(soup)
