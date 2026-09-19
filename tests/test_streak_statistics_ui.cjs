// Exercise the generated controller without a browser or network dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('docs/index.html', 'utf8');
const payload = html.match(/id="ss-data">([\s\S]*?)<\/script>/)[1];
const controller = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .find(match => match[1].includes("getElementById('ss-data')"))[1];
const elements = {};
for (const id of ['data', 'league', 'kind', 'view', 'player', 'player-label', 'period', 'table']) {
  elements['ss-' + id] = {value: '', textContent: '', innerHTML: '', handlers: {},
    addEventListener(type, fn) { this.handlers[type] = fn; }};
}
const stats = (kind, broken, resolved) => ({kind, length:4, horizons:Object.fromEntries(
  [1,2,3].map(h => [h, {broken, resolved, break_pct:100*broken/resolved, incomplete:0}]))});
const person = (key, rows, remaining=4) => ({player:key, player_key:key, current:{SG:4,SP:4}, remaining, rows});
const data = {leagues: {
  GT:{players:[person('ninety', [stats('SG',90,100)]), person('exact85',[stats('SG',85,100)]), person('unknown',[])], rows:[stats('SG',90,100),stats('SP',90,100)]},
  EADRIATIC:{players:[person('highest',[stats('SP',95,100)],2),person('noCalendar',[stats('SG',86,100)],null)], rows:[stats('SG',90,100),stats('SP',90,100)]}
}};
elements['ss-data'].textContent = JSON.stringify(data);
elements['ss-league'].value = 'all';
elements['ss-kind'].value = 'all';
elements['ss-view'].value = 'current';
vm.runInNewContext(controller, {document: {getElementById: id => elements[id]}});
const change = (id, value) => {
  elements['ss-' + id].value = value;
  elements['ss-' + id].handlers.change();
};
const initial = elements['ss-table'].innerHTML;
assert(initial.indexOf('highest') < initial.indexOf('ninety'));
assert(initial.indexOf('ninety') < initial.indexOf('noCalendar'));
assert(!initial.includes('exact85'));
assert(!initial.includes('unknown'));
assert(initial.includes('Sin calendario'));
assert(initial.includes('Quedan menos de 3'));
assert(initial.includes('<td>EADRIATIC</td>'));
assert(initial.includes('<td>GT</td>'));
assert.match(html, /id="ss-league"><option value="all">/);
assert.match(html, /id="ss-kind"><option value="all">/);
change('view','active');
assert(elements['ss-table'].innerHTML.includes('exact85'));
assert(elements['ss-table'].innerHTML.includes('unknown'));
for (const league of ['GT', 'EADRIATIC']) {
  change('league', league);
  for (const kind of ['SG', 'SP']) {
    change('kind', kind);
    change('view', 'general');
    assert.match(elements['ss-table'].innerHTML, /<table>/);
    assert.match(elements['ss-table'].innerHTML, /Incompletos:/);
    assert.match(elements['ss-table'].innerHTML, new RegExp(kind + ' 4'));
    change('player', league + '|' + data.leagues[league].players[0].player_key);
    change('view', 'player');
    assert.equal(elements['ss-player-label'].hidden, false);
    assert.match(elements['ss-table'].innerHTML, /<table>|No hay casos/);
  }
}
change('view', 'current');
const key = 'EADRIATIC|' + data.leagues.EADRIATIC.players[0].player_key;
elements['ss-table'].handlers.click({target: {closest: () => ({dataset: {player: key, kind:'SP'}})}});
assert.equal(elements['ss-view'].value, 'player');
assert.equal(elements['ss-player'].value, key);
assert.equal(elements['ss-kind'].value, 'SP');
change('player', 'missing');
assert.match(elements['ss-table'].innerHTML, /No hay casos/);
console.log('Streak statistics controller: league, kind, view, player, drill-down and empty state passed.');
