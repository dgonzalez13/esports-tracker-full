const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const select = {value: 'original', addEventListener(event, callback) {this.change = callback;}};
const cells = ['>10', '4', '50.00%', '75.00%'].map(alternative => ({
    dataset: {original: 'original value', alternative}, textContent: 'original value'
}));
const section = {querySelector() {return select;}, querySelectorAll() {return cells;}};
vm.runInNewContext(fs.readFileSync('web_tracker/h2h_repeat_samples.js', 'utf8'), {
    document: {getElementById(id) {assert.equal(id, 'active-repeat-matches'); return section;}}
});
select.value = 'alternative';
select.change();
assert.deepEqual(cells.map(cell => cell.textContent), ['>10', '4', '50.00%', '75.00%']);
select.value = 'original';
select.change();
assert(cells.every(cell => cell.textContent === 'original value'));
console.log('Repeat sample selector checks passed');
