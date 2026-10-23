(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (typeof document !== 'undefined') {
        const section = document.getElementById('team-statistics');
        if (section) api.mount(section);
    }
})(globalThis, function () {
    'use strict';
    const selected = value => value !== '' && value !== undefined && value !== null;

    function selectMatches(data, filters = {}) {
        if (!selected(filters.player)) return [];
        const player = Number(filters.player);
        const rows = [];
        for (const match of data.matches || []) {
            const [league, date, a, teamA, b, teamB, result] = match;
            if (filters.league && league !== filters.league) continue;
            if (filters.from && date < filters.from || filters.to && date > filters.to) continue;
            let row;
            if (a === player) row = {league, date, player: a, team: teamA, rival: b, rivalTeam: teamB, result};
            else if (b === player) row = {league, date, player: b, team: teamB, rival: a, rivalTeam: teamA,
                result: {V: 'D', E: 'E', D: 'V'}[result]};
            else continue;
            if (selected(filters.team) && row.team !== Number(filters.team)) continue;
            if (selected(filters.rival) && row.rival !== Number(filters.rival)) continue;
            if (selected(filters.rivalTeam) && row.rivalTeam !== Number(filters.rivalTeam)) continue;
            rows.push(row);
        }
        return rows;
    }

    function summarize(rows) {
        const totals = {played: 0, wins: 0, draws: 0, losses: 0};
        for (const row of rows) {
            totals.played++;
            totals[{V: 'wins', E: 'draws', D: 'losses'}[row.result]]++;
        }
        for (const field of ['wins', 'draws', 'losses']) {
            totals[field + 'Pct'] = totals.played ? totals[field] * 100 / totals.played : null;
        }
        totals.gap = totals.played ? (totals.wins - totals.losses) * 100 / totals.played : null;
        return totals;
    }

    function aggregateMatches(rows, grouping = 'both', minimum = 1) {
        const groups = new Map();
        for (const row of rows) {
            const key = JSON.stringify(grouping === 'rival' ? [row.team, row.rival] :
                grouping === 'team' ? [row.team, row.rivalTeam] : [row.team, row.rival, row.rivalTeam]);
            if (!groups.has(key)) groups.set(key, {team: row.team, rival: row.rival, rivalTeam: row.rivalTeam, rows: []});
            groups.get(key).rows.push(row);
        }
        return [...groups.values()].map(group => ({team: group.team, rival: group.rival, rivalTeam: group.rivalTeam,
            ...summarize(group.rows)})).filter(group => group.played >= Math.max(1, Number(minimum) || 1));
    }

    function mount(section) {
        const data = JSON.parse(section.querySelector('#team-stats-data').textContent);
        const ids = {league: 'league', player: 'player', team: 'team', rival: 'rival', rivalTeam: 'rival-team',
            grouping: 'group', from: 'from', to: 'to', minimum: 'minimum', sort: 'sort'};
        const controls = Object.fromEntries(Object.entries(ids).map(([name, id]) =>
            [name, section.querySelector('#team-stats-' + id)]));
        const summary = section.querySelector('#team-stats-summary');
        const output = section.querySelector('#team-stats-table');
        const pct = value => value === null ? '—' : value.toFixed(2) + '%';
        const gap = value => value === null ? '—' : (value >= 0 ? '+' : '') + value.toFixed(2);
        const names = (catalog, index) => catalog[index]?.name || 'Sin nombre';
        function fill(control, options, placeholder) {
            const previous = control.value;
            control.replaceChildren(new Option(placeholder, ''));
            for (const [value, label] of options) control.add(new Option(label, String(value)));
            control.value = options.some(([value]) => String(value) === previous) ? previous : '';
        }
        function optionList(values, catalog) {
            return [...new Set(values)].map(id => [id, names(catalog, id)])
                .sort((a, b) => a[1].localeCompare(b[1]));
        }
        function state() {
            return Object.fromEntries(Object.entries(controls).map(([name, control]) => [name, control.value]));
        }
        function refreshOptions() {
            const league = controls.league.value;
            fill(controls.player, data.players.map((player, id) => [id, player])
                .filter(([, player]) => !league || player.league === league)
                .map(([id, player]) => [id, player.name + (league ? '' : ' · ' + player.league)])
                .sort((a, b) => a[1].localeCompare(b[1])), 'Selecciona un jugador');
            const base = state();
            const forPlayer = selectMatches(data, {...base, team: '', rival: '', rivalTeam: ''});
            fill(controls.team, optionList(forPlayer.map(row => row.team), data.teams), 'Todos sus equipos');
            const forTeam = selectMatches(data, {...state(), rival: '', rivalTeam: ''});
            fill(controls.rival, optionList(forTeam.map(row => row.rival), data.players), 'Todos los rivales');
            fill(controls.rivalTeam, optionList(forTeam.map(row => row.rivalTeam), data.teams), 'Todos los equipos rivales');
        }
        function render() {
            output.replaceChildren();
            const filters = state();
            if (!selected(filters.player)) {
                summary.textContent = `${data.unique_matches} partidos únicos disponibles. Selecciona un jugador y, si quieres, uno de sus equipos.`;
                return;
            }
            if (filters.from && filters.to && filters.from > filters.to) {
                summary.textContent = 'La fecha inicial debe ser anterior o igual a la final.';
                return;
            }
            const rows = selectMatches(data, filters);
            const total = summarize(rows);
            summary.textContent = `${names(data.players, Number(filters.player))} · ${selected(filters.team) ? names(data.teams, Number(filters.team)) : 'Todos sus equipos'}: ` +
                `${total.played} ${total.played === 1 ? 'partido único' : 'partidos únicos'} · ${total.wins} V / ${total.draws} E / ${total.losses} D · ` +
                `V ${pct(total.winsPct)} · E ${pct(total.drawsPct)} · D ${pct(total.lossesPct)} · Dif. ${gap(total.gap)} pp.`;
            const groups = aggregateMatches(rows, filters.grouping, filters.minimum);
            groups.sort((a, b) => (filters.sort === 'win-desc' ? b.winsPct - a.winsPct :
                filters.sort === 'win-asc' ? a.winsPct - b.winsPct :
                filters.sort === 'gap' ? b.gap - a.gap : b.played - a.played) || b.played - a.played ||
                names(data.players, a.rival).localeCompare(names(data.players, b.rival)) ||
                names(data.teams, a.rivalTeam).localeCompare(names(data.teams, b.rivalTeam)));
            if (!groups.length) {
                const p = document.createElement('p');
                p.textContent = rows.length ? 'Ninguna agrupación alcanza el mínimo de partidos indicado.' :
                    'No hay partidos para esta selección.';
                output.append(p);
                return;
            }
            const headers = ['Equipo del jugador', ...(filters.grouping !== 'team' ? ['Jugador rival'] : []),
                ...(filters.grouping !== 'rival' ? ['Equipo rival'] : []),
                'Partidos', 'V', 'E', 'D', 'V%', 'E%', 'D%', 'Dif. V−D (pp)'];
            const table = document.createElement('table');
            const head = table.createTHead().insertRow();
            for (const label of headers) {
                const th = document.createElement('th');
                th.textContent = label;
                head.append(th);
            }
            const body = table.createTBody();
            for (const row of groups) {
                const cells = [names(data.teams, row.team), ...(filters.grouping !== 'team' ? [names(data.players, row.rival)] : []),
                    ...(filters.grouping !== 'rival' ? [names(data.teams, row.rivalTeam)] : []),
                    row.played, row.wins, row.draws, row.losses, pct(row.winsPct), pct(row.drawsPct),
                    pct(row.lossesPct), gap(row.gap)];
                const tr = body.insertRow();
                cells.forEach((value, index) => {
                    const td = tr.insertCell();
                    td.textContent = value;
                    if (index >= cells.length - 8) td.className = 'num';
                });
            }
            output.append(table);
        }
        for (const [name, control] of Object.entries(controls)) {
            control.addEventListener('change', () => {
                if (['league', 'player', 'team', 'from', 'to'].includes(name)) refreshOptions();
                render();
            });
        }
        controls.minimum.addEventListener('input', render);
        section.querySelector('#team-stats-reset').addEventListener('click', () => {
            for (const control of Object.values(controls)) control.value = '';
            controls.grouping.value = 'both';
            controls.minimum.value = '1';
            controls.sort.value = 'played';
            refreshOptions();
            render();
        });
        for (const control of [controls.from, controls.to]) {
            if (data.first_date) control.min = data.first_date;
            if (data.last_date) control.max = data.last_date;
        }
        refreshOptions();
        render();
    }
    return {selectMatches, summarize, aggregateMatches, mount};
});
