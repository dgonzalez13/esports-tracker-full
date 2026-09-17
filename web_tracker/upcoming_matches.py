"""Published fixtures for all players, filtered against the viewer's current time."""

from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo


def upcoming_fixtures(schedule, reference):
    fixtures = {}
    for league, source in schedule.get("sources", {}).items():
        for row in source.get("records", []):
            if row.get("fixture_status") != "scheduled" or row.get("result"):
                continue
            try:
                stamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            player, rival = row.get("player"), row.get("rival")
            if stamp < reference or not player or not rival:
                continue
            identity = (league, row.get("match_id") or (
                stamp.isoformat(), tuple(sorted((player.casefold(), rival.casefold())))
            ))
            fixtures.setdefault(identity, {
                "league": league, "player": player, "rival": rival, "timestamp": stamp,
            })
    return sorted(fixtures.values(), key=lambda row: (
        row["timestamp"], row["league"], row["player"].casefold(), row["rival"].casefold(),
    ))


def render_upcoming_matches(schedule, reference=None):
    reference = reference or datetime.now(timezone.utc)
    rows = []
    for row in upcoming_fixtures(schedule, reference):
        local = row["timestamp"].astimezone(ZoneInfo("Europe/Madrid"))
        rows.append(
            f'<tr class="upcoming-match" data-start="{int(row["timestamp"].timestamp() * 1000)}" '
            f'data-league="{escape(row["league"])}" hidden>'
            f'<td><time datetime="{row["timestamp"].isoformat()}" title="{local:%d/%m/%Y %H:%M} (Madrid)">{local:%H:%M}</time></td>'
            f'<td>{escape(row["league"])}</td>'
            f'<td>{escape(row["player"])} <span class="upcoming-vs">vs</span> '
            f'{escape(row["rival"])}</td></tr>'
        )
    updates = []
    for league in ("GT", "EADRIATIC"):
        source = schedule.get("sources", {}).get(league, {})
        try:
            stamp = datetime.fromisoformat(source["updated_at"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            updated = stamp.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m %H:%M")
        except (KeyError, TypeError, ValueError, AttributeError):
            updated = "sin actualización disponible"
        suffix = " (falló la última actualización)" if source.get("error") else ""
        updates.append(f"{league}: {updated}{suffix}")
    return (
        '<section class="dashboard-section" id="upcoming-matches">'
        '<h2>Próximos partidos</h2>'
        '<p class="section-subtitle">Todos los jugadores · Horario de Madrid · Calendario publicado, no en directo.</p>'
        '<div class="upcoming-filters"><label>Ventana <select id="upcoming-window">'
        '<option value="1">Próxima hora</option><option value="2">Próximas 2 horas</option>'
        '</select></label><label>Liga <select id="upcoming-league">'
        '<option value="">Todas las ligas</option><option value="GT">GT</option>'
        '<option value="EADRIATIC">EADRIATIC</option></select></label></div>'
        '<p id="upcoming-status" role="status"></p>'
        '<table class="upcoming-table" aria-label="Próximos partidos">'
        '<colgroup><col class="upcoming-time-col"><col class="upcoming-league-col"><col></colgroup>'
        '<thead><tr><th scope="col">Hora</th><th scope="col">Liga</th>'
        '<th scope="col">Partido</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        '<p class="section-subtitle">Última actualización del calendario (Madrid): '
        + escape(" · ".join(updates)) + '</p>'
        '<noscript>Activa JavaScript para consultar los partidos de la próxima hora o las próximas 2 horas.</noscript>'
        '</section>' + SCRIPT
    )


SCRIPT = """<script>
(() => {
    const section = document.getElementById('upcoming-matches');
    const windowSelect = section.querySelector('#upcoming-window');
    const leagueSelect = section.querySelector('#upcoming-league');
    const rows = [...section.querySelectorAll('.upcoming-match')];
    function update() {
        const now = Date.now();
        const end = now + Number(windowSelect.value) * 3600000;
        let count = 0;
        for (const row of rows) {
            const start = Number(row.dataset.start);
            row.hidden = !(start >= now && start <= end &&
                (!leagueSelect.value || row.dataset.league === leagueSelect.value));
            if (!row.hidden) count++;
        }
        section.querySelector('#upcoming-status').textContent = count
            ? `${count} partido${count === 1 ? '' : 's'} en el calendario disponible.`
            : 'No hay partidos en el calendario disponible para esta ventana y liga.';
    }
    windowSelect.addEventListener('change', update);
    leagueSelect.addEventListener('change', update);
    document.addEventListener('visibilitychange', update);
    update();
    setInterval(update, 30000);
})();
</script>"""
