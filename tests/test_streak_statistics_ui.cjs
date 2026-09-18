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
elements['ss-data'].textContent = payload;
elements['ss-league'].value = 'GT';
elements['ss-kind'].value = 'SG';
elements['ss-view'].value = 'current';
vm.runInNewContext(controller, {document: {getElementById: id => elements[id]}});
const change = (id, value) => {
  elements['ss-' + id].value = value;
  elements['ss-' + id].handlers.change();
};
const data = JSON.parse(payload);
for (const league of ['GT', 'EADRIATIC']) {
  change('league', league);
  for (const kind of ['SG', 'SP']) {
    change('kind', kind);
    change('view', 'general');
    assert.match(elements['ss-table'].innerHTML, /<table>/);
    assert.match(elements['ss-table'].innerHTML, /Incompletos:/);
    assert.match(elements['ss-table'].innerHTML, new RegExp(kind + ' 4'));
    change('player', data.leagues[league].players[0].player_key);
    change('view', 'player');
    assert.equal(elements['ss-player-label'].hidden, false);
    assert.match(elements['ss-table'].innerHTML, /<table>/);
  }
}
change('view', 'current');
const key = data.leagues.EADRIATIC.players[0].player_key;
elements['ss-table'].handlers.click({target: {closest: () => ({dataset: {player: key}})}});
assert.equal(elements['ss-view'].value, 'player');
assert.equal(elements['ss-player'].value, key);
change('player', 'missing');
assert.match(elements['ss-table'].innerHTML, /No hay casos/);
console.log('Streak statistics controller: league, kind, view, player, drill-down and empty state passed.');
