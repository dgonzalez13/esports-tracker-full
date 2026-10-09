const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function makeSection() {
    const controls = [0, 5, 10].map(value => ({value: String(value), checked: false,
        addEventListener(event, callback) { this.change = callback; }}));
    const rows = [-5, 0, 4.99, 5, 9.99, 10, '—'].map(value => ({
        cells: [null, null, null, null, {textContent: String(value)}], hidden: false
    }));
    const empty = {hidden: true};
    return {controls, rows, empty,
        querySelectorAll(selector) { return selector.includes('input') ? controls : rows; },
        querySelector() { return empty; }};
}
const sections = {first: makeSection(), second: makeSection()};
const context = {document: {getElementById(id) { return sections[id]; }}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('web_tracker/h2h_gap_filters.js', 'utf8'), context);
context.initH2HGapFilters('first');
context.initH2HGapFilters('second');
const first = sections.first;
assert(first.rows.every(row => !row.hidden));
for (const [index, expected] of [[0, 5], [1, 3], [2, 1]]) {
    first.controls[index].checked = true;
    first.controls[index].change();
    assert.equal(first.controls.filter(control => control.checked).length, 1);
    assert.equal(first.rows.filter(row => !row.hidden).length, expected);
    assert(sections.second.rows.every(row => !row.hidden));
}
first.controls[2].checked = false;
first.controls[2].change();
assert(first.rows.every(row => !row.hidden));
first.rows.forEach(row => row.cells[4].textContent = '-1');
first.controls[0].checked = true;
first.controls[0].change();
assert.equal(first.empty.hidden, false);
console.log('Gap filter checks passed');
