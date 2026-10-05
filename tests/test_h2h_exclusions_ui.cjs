const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web_tracker/h2h_exclusions.js', 'utf8');
const entry = {league: 'GT', group: 1, members: ['A', 'B', 'C', 'D', 'E'], player: 'A', rival: 'B'};

function element() {
  return {listeners: {}, value: '', disabled: false, textContent: '', isConnected: true,
    addEventListener(type, fn) { this.listeners[type] = fn; },
    dispatchEvent(event) { this.listeners[event.type]?.(event); },
    setAttribute() {}, append(child) { this.child = child; }, replaceChildren(child) { this.child = child; },
    remove() { this.isConnected = false; }};
}
async function run(failWrite = false) {
  const row = element(); row.cells = [element()];
  const fields = Object.fromEntries(['input', '[type="submit"]', '.pair-cancel', '.pair-error', '.pair-question', '.pair-auth', 'form'].map(k => [k, element()]));
  const dialog = element(); dialog.querySelector = selector => fields[selector];
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.listeners.close?.(); };
  const zero = element(); const filters = element();
  const section = {querySelectorAll: () => [row], querySelector: selector => selector === '.upcoming-filters' ? filters : zero};
  let content = entry.members.map(p => `GT|${p}`).join('\n') + '\n';
  const writes = [];
  const context = {TextEncoder, TextDecoder, Uint8Array, Event, JSON,
    atob: text => Buffer.from(text, 'base64').toString('binary'), btoa: text => Buffer.from(text, 'binary').toString('base64'),
    document: {body: {append() {}}, getElementById: id => id === 'recent-group-h2h' ? section : {textContent: JSON.stringify([entry])},
               createElement: tag => tag === 'dialog' ? dialog : element()},
    fetch: async (url, options) => {
      if (options.method === 'PUT') {
        const body = JSON.parse(options.body); writes.push(body);
        assert.equal(body.sha, 'current-sha'); assert.equal(body.branch, 'main');
        assert.equal(options.headers.Authorization, 'Bearer test-token');
        if (failWrite) return {ok: false, status: 403};
        content = Buffer.from(body.content, 'base64').toString('utf8');
        return {ok: true, status: 200};
      }
      return {ok: true, json: async () => ({sha: 'current-sha', content: Buffer.from(content).toString('base64')})};
    }};
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  row.cells[0].child.onclick();
  fields['.pair-cancel'].onclick();
  assert.equal(writes.length, 0); // Cancel never writes or removes.
  assert.equal(row.isConnected, true);
  row.cells[0].child.onclick(); fields.input.value = 'test-token';
  await fields.form.listeners.submit({preventDefault() {}});
  assert.equal(fields.input.value, '');
  assert.equal(writes.length, 1);
  assert.equal(row.isConnected, failWrite);
  if (failWrite) assert.match(fields['.pair-error'].textContent, /403/);
  else {
    const directive = content.split('\n').find(line => line.startsWith('@H2H_EXCLUDE||'));
    assert.deepEqual(JSON.parse(directive.slice('@H2H_EXCLUDE||'.length)), entry);
    assert.equal(fields['.pair-auth'].hidden, true);
    assert.equal(fields.input.required, false);
    // Another exclusion in the same tab uses the existing token, no new paste.
    content = entry.members.map(p => `GT|${p}`).join('\n') + '\n';
    row.isConnected = true; row.cells[0].child.onclick();
    assert.equal(fields.input.value, '');
    await fields.form.listeners.submit({preventDefault() {}});
    assert.equal(writes.length, 2);
    filters.child.onclick();
    assert.equal(fields['.pair-auth'].hidden, false);
    assert.equal(fields.input.required, true);
  }
}
(async () => { await run(); await run(true); process.stdout.write('H2H exclusion UI checks passed\n'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
