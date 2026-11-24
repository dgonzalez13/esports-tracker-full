const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let now = Date.parse('2026-11-24T12:00:00Z');
Date.now = () => now;
let tick;
global.setInterval = callback => { tick = callback; };
const classes = new Set();
const row = {hidden: false, cells: Array.from({length: 7}, () => ({textContent: ''})),
  classList: {toggle: (key, on) => on ? classes.add(key) : classes.delete(key)},
  parentNode: {appendChild: () => {}}};
const metadata = [{events: [
  {timestamp: '2026-11-24T08:00:00Z', result: 'V'},
  {timestamp: '2026-11-24T11:50:00Z', result: null},
  {timestamp: '2026-11-24T13:00:00Z', result: null}],
  fixtures: [{timestamp: '2026-11-24T11:50:00Z', estimated: false},
             {timestamp: '2026-11-24T13:00:00Z', estimated: false}]}];
global.document = {getElementById: id => id === 'daily-pair-watch'
  ? {querySelectorAll: () => [row]} : {textContent: JSON.stringify(metadata)}, addEventListener: () => {}};
eval(fs.readFileSync(path.join(__dirname, '../web_tracker/daily_pair_watch.js'), 'utf8'));
assert.equal(row.hidden, false);
assert.equal(row.cells[5].textContent, 'V');
assert.equal(row.cells[6].textContent, '12:50');
assert.equal(classes.has('daily-pair-pending'), false);
now = Date.parse('2026-11-24T12:05:00Z'); tick();
assert.equal(row.cells[5].textContent, 'V?');
assert.equal(row.cells[6].textContent, '14:00');
assert.equal(classes.has('daily-pair-pending'), true);
assert.equal(classes.has('daily-pair-green'), false);
now = Date.parse('2026-11-24T13:15:00Z'); tick();
assert.equal(row.hidden, true);
console.log('Daily pair live cutoff and pending-result checks passed');

now = Date.parse('2026-11-25T01:00:00Z');
metadata[0] = {events: [
  {timestamp: '2026-11-24T16:00:00Z', result: 'V'},
  {timestamp: '2026-11-24T21:00:00Z', result: 'E'}],
  fixtures: [{timestamp: '2026-11-25T08:00:00Z', estimated: false}]};
eval(fs.readFileSync(path.join(__dirname, '../web_tracker/daily_pair_watch.js'), 'utf8'));
assert.equal(row.cells[5].textContent, 'E');
assert.equal(classes.has('daily-pair-green'), true);
now = Date.parse('2026-11-25T05:01:00Z'); tick();
assert.equal(row.cells[5].textContent, 'Sin resultados (8 h)');
console.log('Rolling eight-hour window across midnight checks passed');
