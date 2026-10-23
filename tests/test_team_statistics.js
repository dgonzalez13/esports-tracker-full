const assert = require('node:assert/strict');
const {selectMatches, summarize, aggregateMatches} = require('../web_tracker/team_statistics.js');

const data = {
    players: [{name: 'Alice', league: 'GT'}, {name: 'Bob', league: 'GT'}, {name: 'Carol', league: 'GT'},
        {name: 'Alice', league: 'EADRIATIC'}, {name: 'Bob', league: 'EADRIATIC'}],
    teams: [{name: 'Red', league: 'GT'}, {name: 'Blue', league: 'GT'}, {name: 'Black', league: 'GT'},
        {name: 'Red', league: 'EADRIATIC'}, {name: 'Blue', league: 'EADRIATIC'}],
    matches: [
        ['GT', '2026-10-15', 0, 0, 1, 1, 'V'],
        ['GT', '2026-10-16', 0, 0, 1, 2, 'E'],
        ['GT', '2026-10-17', 0, 1, 2, 1, 'D'],
        ['EADRIATIC', '2026-10-15', 3, 3, 4, 4, 'V']
    ]
};

assert.deepEqual(selectMatches(data), []); // No combined A→B + B→A totals.
const alice = selectMatches(data, {player: '0'});
assert.equal(alice.length, 3);
assert.deepEqual([summarize(alice).wins, summarize(alice).draws, summarize(alice).losses], [1, 1, 1]);
const bob = summarize(selectMatches(data, {player: '1'}));
assert.deepEqual([bob.played, bob.wins, bob.draws, bob.losses], [2, 0, 1, 1]);
assert.equal(selectMatches(data, {player: '0', league: 'EADRIATIC'}).length, 0);
assert.equal(selectMatches(data, {player: '3', team: '3'}).length, 1);

const red = selectMatches(data, {player: '0', team: '0'});
assert.equal(red.length, 2);
assert.equal(summarize(red).winsPct, 50);
assert.equal(aggregateMatches(red, 'rival').length, 1);
assert.equal(aggregateMatches(red, 'team').length, 2);
assert.equal(aggregateMatches(red, 'both').length, 2);
for (const mode of ['rival', 'team', 'both']) {
    assert.equal(aggregateMatches(red, mode).reduce((n, row) => n + row.played, 0), 2);
}
assert.equal(aggregateMatches(red, 'team', 2).length, 0);
assert.equal(summarize(red).played, 2); // Minimum sample hides groups, never changes selection totals.
assert.equal(selectMatches(data, {player: '0', team: '0', rival: '1', rivalTeam: '2'})[0].result, 'E');
assert.equal(selectMatches(data, {player: '0', from: '2026-10-16', to: '2026-10-16'})[0].result, 'E');
assert.equal(selectMatches(data, {player: '0', from: '2026-11-01'}).length, 0);
assert.equal(summarize([]).winsPct, null);
console.log('Team statistics filters, orientation and non-duplicated grouping: OK');
