const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
function block(firstMatches) {
  const checkbox = {checked: false, addEventListener: (_, callback) => { checkbox.change = callback; }};
  const rows = firstMatches.map(first => ({dataset: {firstMatch: String(first)}, hidden: false}));
  const empty = {hidden: true};
  return {checkbox, rows, empty,
    querySelector: selector => selector === '.hide-first-match' ? checkbox : empty,
    querySelectorAll: () => rows};
}
const blocks = [block([true, false]), block([true]), block([])];
global.document = {querySelectorAll: () => blocks};
eval(fs.readFileSync(path.join(__dirname, '../web_tracker/candidate_start_filter.js'), 'utf8'));
assert.deepEqual(blocks[0].rows.map(row => row.hidden), [false, false]);
blocks[0].checkbox.checked = true;
blocks[0].checkbox.change();
assert.deepEqual(blocks[0].rows.map(row => row.hidden), [true, false]);
assert.equal(blocks[1].rows[0].hidden, false);
assert.equal(blocks[0].empty.hidden, true);
blocks[0].checkbox.checked = false;
blocks[0].checkbox.change();
assert.deepEqual(blocks[0].rows.map(row => row.hidden), [false, false]);
blocks[1].checkbox.checked = true;
blocks[1].checkbox.change();
assert.equal(blocks[1].empty.hidden, false);
assert.equal(blocks[2].empty.hidden, true);
console.log('Candidate start filter checks passed');
