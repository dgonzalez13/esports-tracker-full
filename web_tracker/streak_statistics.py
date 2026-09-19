"""Interactive historical run statistics, with no external dependencies."""

import json


def render_streak_statistics(payload):
    data = json.dumps(payload or {"leagues": {}}, ensure_ascii=True).replace("<", "\\u003c")
    return '''<section class="dashboard-section" id="streak-statistics">
<div class="section-head"><div><h2>Estadísticas de rachas · Turnos de 8 horas</h2>
<p class="section-subtitle">SG se rompe con una victoria. SP se rompe con una derrota. Los empates prolongan ambas.</p></div></div>
<div class="streak-filters">
<label>Liga <select id="ss-league"><option value="all">Todas las ligas</option><option>GT</option><option>EADRIATIC</option></select></label>
<label>Racha <select id="ss-kind"><option value="all">SG y SP</option><option value="SG">SG · Sin ganar</option><option value="SP">SP · Sin perder</option></select></label>
<label>Vista <select id="ss-view"><option value="current">Activos · Más del 85 % en 3</option><option value="active">Todos los activos</option><option value="general">General de la liga</option><option value="player">Por jugador</option></select></label>
<label id="ss-player-label" hidden>Jugador <select id="ss-player"></select></label>
</div>
<p id="ss-period" class="section-subtitle"></p>
<div id="ss-table" class="table-wrap" aria-live="polite"></div>
<details><summary>Cómo se calculan estos porcentajes</summary>
<p>Horarios de Madrid. Eadriatic: 07:00 / 07:20, 15:00 / 15:20 y 23:00 / 23:20.
GT: 05:00 / 06:00, 13:00 / 14:00 y 21:00 / 22:00. Cada grupo tiene su propia ventana,
desde su inicio hasta el siguiente turno, con un máximo de 8 horas. Medianoche no reinicia la racha.</p>
<p>Los grupos históricos se reconstruyen por sus enfrentamientos. Se exige un partido registrado
en la hora de inicio y un grupo separable de 4 o 5 jugadores. Los bloques ambiguos se excluyen.
El cálculo usa los partidos disponibles: las ausencias en la fuente pueden afectar las rachas.</p>
<p>Cada racha aporta una observación al alcanzar N. En cada horizonte se muestra rupturas / casos resueltos,
y aparte los casos incompletos. Una ruptura temprana resuelve el caso; si no hay ruptura y faltan partidos
antes del corte, queda incompleto. Los porcentajes describen los casos resueltos y pueden estar sesgados
si los incompletos se comportan de otra manera. Los horizontes tienen denominadores distintos.</p>
<p>En 2 y 3 partidos se incluyen las rupturas anteriores. «Continúa» significa que se observaron
todos esos partidos sin ruptura. «Pocos datos» indica menos de 30 casos resueltos, no una garantía
de fiabilidad por encima de ese umbral. El resumen general reúne observaciones de jugadores;
dos rivales pueden aportar observaciones del mismo partido.</p>
<p>Solo aparecen jugadores de tracked_players habilitados para apostar. La vista inicial reúne ambas ligas y ambas rachas, con porcentaje estrictamente superior al 85 % en 3 partidos, ordenado de mayor a menor. Un jugador puede tener una fila SG y otra SP.</p>
<p>Los pendientes son partidos futuros publicados en el calendario dentro del turno, sin duplicados ni resultados ya confirmados. «Sin calendario» indica falta de cobertura o error de actualización; un calendario parcial puede omitir partidos. Los datos corresponden a la actualización indicada, no a un seguimiento en directo.</p>
<p>La racha del turno actual se limita a su grupo y puede diferir de Current Streaks, que muestra
las últimas 8 horas móviles. No se enlazan turnos ni se cuentan actualizaciones repetidas.</p>
</details></section>
<style>
.streak-filters{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0}
.streak-filters label{display:flex;flex-direction:column;gap:5px;font-weight:600}
.streak-filters label[hidden]{display:none}
.streak-filters select{padding:8px;border:1px solid #b8c2cf;border-radius:6px;background:white;color:#172536;font:inherit}
#ss-table small{display:block;font-size:12px;font-weight:400;white-space:normal;color:#526174;margin-top:4px}
#ss-table button{border:0;background:none;color:#175ca4;text-decoration:underline;cursor:pointer;font:inherit}
#streak-statistics details{margin-top:18px;max-width:1000px}
#streak-statistics summary{cursor:pointer}
</style>
<script type="application/json" id="ss-data">''' + data + '''</script>
<script>
(() => {
const data = JSON.parse(document.getElementById('ss-data').textContent);
const get = id => document.getElementById('ss-' + id);
const league = get('league'), kind = get('kind'), view = get('view'), player = get('player');
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = value => value.toLocaleString('es-ES', {maximumFractionDigits:1}) + ' %';
const cell = h => {
 if (!h) return '<td>—<small>Sin casos históricos</small></td>';
 const main = h.resolved ? '<strong>' + pct(h.break_pct) + '</strong><small>' + h.broken + ' / ' + h.resolved + ' resueltos</small><small>Continúa: ' + pct(100-h.break_pct) + '</small>' : '—<small>Sin casos resueltos</small>';
 return '<td>' + main + '<small>Incompletos: ' + h.incomplete + (h.resolved < 30 ? ' · Pocos datos' : '') + '</small></td>';
};
const selectedGroups = () => Object.entries(data.leagues).filter(([name]) => league.value === 'all' || name === league.value);
const selectedPlayers = () => selectedGroups().flatMap(([name, group]) => (group.players || []).map(p => ({...p, league:name})));
const identity = p => p.league + '|' + p.player_key;
function populate() {
 const previous = player.value;
 const players = selectedPlayers();
 player.innerHTML = players.map(p => '<option value="' + esc(identity(p)) + '">' + esc(p.player + ' · ' + p.league) + '</option>').join('');
 player.value = players.some(p => identity(p) === previous) ? previous : (players[0] ? identity(players[0]) : '');
 render();
}
function render() {
 const players = selectedPlayers();
 const currentView = view.value === 'current' || view.value === 'active';
 get('player-label').hidden = view.value !== 'player';
 const date = raw => raw ? new Date(raw).toLocaleString('es-ES', {timeZone:'Europe/Madrid'}) : '—';
 get('period').textContent = 'Actualizado: ' + date(data.generated_at) + ' (Madrid). ' + selectedGroups().map(([name, g]) => name + ': ' + date(g.from) + ' → ' + date(g.to) + ', ' + (g.windows || 0) + ' ventanas históricas de jugador.').join(' ');
 const headings = '<th>Rompe en 1 partido</th><th>Rompe en próximos 2</th><th>Rompe en próximos 3</th>';
 let rows = [], first;
 if (currentView) {
  first = '<th>Jugador</th><th>Liga</th><th>Racha del turno</th><th>Partidos pendientes</th>';
  const candidates = players.flatMap(p => ['SG', 'SP'].filter(k => kind.value === 'all' || kind.value === k).map(k => {
   const length = (p.current || {})[k] || 0;
   const stats = p.rows.find(r => r.kind === k && r.length === length);
   const h = stats && stats.horizons[3];
   return {p, k, length, stats, percentage: h && h.resolved ? 100 * h.broken / h.resolved : null};
  })).filter(r => r.length > 0 && (view.value === 'active' || (r.percentage !== null && r.percentage > 85)));
  candidates.sort((a,b) => (b.percentage ?? -1) - (a.percentage ?? -1) || a.p.player.localeCompare(b.p.player) || a.k.localeCompare(b.k));
  rows = candidates.map(({p,k,length,stats}) => {
   const remaining = p.remaining == null ? '—<small>Sin calendario</small>' : p.remaining + '<small>Publicados' + (p.remaining < 3 ? ' · Quedan menos de 3' : '') + '</small>';
   return '<tr><td><button type="button" data-player="' + esc(identity(p)) + '" data-kind="' + k + '">' + esc(p.player) + '</button></td><td>' + esc(p.league) + '</td><td>' + k + ' ' + length + '</td><td>' + remaining + '</td>' + [1,2,3].map(h => cell(stats && stats.horizons[h])).join('') + '</tr>';
  });
 } else {
  first = '<th>Liga</th><th>Racha alcanzada</th>';
  const sources = view.value === 'general' ? selectedGroups().map(([league, group]) => ({...group, league})) : players.filter(p => identity(p) === player.value);
  rows = sources.flatMap(source => (source.rows || []).filter(r => kind.value === 'all' || r.kind === kind.value).map(r => '<tr><td>' + esc(source.league) + '</td><td>' + r.kind + ' ' + r.length + '</td>' + [1,2,3].map(h => cell(r.horizons[h])).join('') + '</tr>'));
 }
 const hasCurrent = players.some(p => Object.values(p.current || {}).some(n => n > 0));
 const empty = currentView && !hasCurrent ? 'No hay rachas del turno actual disponibles para los jugadores de tracked_players. Comprueba la hora de actualización de los resultados y los jugadores seleccionados.' : view.value === 'current' ? 'Ningún jugador activo supera el 85 % en los próximos 3 partidos para esta selección. Puedes elegir «Todos los activos».' : 'No hay casos disponibles para esta selección.';
 get('table').innerHTML = rows.length ? '<table><thead><tr>' + first + headings + '</tr></thead><tbody>' + rows.join('') + '</tbody></table>' : '<p>' + empty + '</p>';
}
league.addEventListener('change', populate);
[kind, view, player].forEach(el => el.addEventListener('change', render));
get('table').addEventListener('click', event => {
 const button = event.target.closest('button[data-player]');
 if (button) { player.value = button.dataset.player; kind.value = button.dataset.kind; view.value = 'player'; render(); }
});
populate();
})();
</script>'''
