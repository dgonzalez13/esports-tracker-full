(() => {
  const section = document.getElementById('recent-group-h2h');
  if (!section) return;
  const entries = JSON.parse(document.getElementById('h2h-exclusion-entries').textContent);
  const rows = [...section.querySelectorAll(':scope > .table-wrap tbody tr')];
  const dialog = document.createElement('dialog');
  dialog.innerHTML = '<form method="dialog"><h3>Excluir pareja</h3><p class="pair-question"></p>' +
    '<p>Se guardará en tracked_players.txt. Solo se oculta esta dirección en la tabla destacada.</p>' +
    '<div class="pair-auth"><label>Token de GitHub <input type="password" autocomplete="off" required></label>' +
    '<p>Se pide una vez por pestaña. Solo se conserva en memoria hasta recargar, cerrar o desconectar. '
    + 'Token limitado al repositorio, con Contents: Read and write.</p></div>' +
    '<p class="pair-error" role="alert"></p><button type="button" class="pair-cancel">Cancelar</button> ' +
    '<button type="submit">Sí, excluir</button></form>';
  document.body.append(dialog);
  let active = null;
  let sessionToken = '';
  const input = dialog.querySelector('input');
  const submit = dialog.querySelector('[type="submit"]');
  const auth = dialog.querySelector('.pair-auth');
  const disconnect = document.createElement('button');
  disconnect.type = 'button'; disconnect.textContent = 'Desconectar GitHub'; disconnect.hidden = true;
  section.querySelector('.upcoming-filters').append(disconnect);
  function updateAuth() {
    auth.hidden = !!sessionToken;
    input.required = !sessionToken;
    disconnect.hidden = !sessionToken;
  }
  disconnect.onclick = () => { sessionToken = ''; input.value = ''; updateAuth(); };
  updateAuth();
  dialog.querySelector('.pair-cancel').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { input.value = ''; active = null; });
  dialog.addEventListener('cancel', event => { if (submit.disabled) event.preventDefault(); });
  rows.forEach((row, index) => {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = '×'; button.className = 'exclude-h2h';
    button.title = 'Excluir esta pareja de destacados';
    button.setAttribute('aria-label', `Excluir ${entries[index].player} frente a ${entries[index].rival}`);
    row.cells[row.cells.length - 1].replaceChildren(button);
    button.onclick = () => {
      active = {row, entry: entries[index]};
      dialog.querySelector('.pair-question').textContent = `¿Seguro que quieres excluir ${active.entry.player} frente a ${active.entry.rival}?`;
      dialog.querySelector('.pair-error').textContent = '';
      input.value = ''; updateAuth(); dialog.showModal();
    };
  });
  // Consult the current file even while Pages still serves the previous build.
  fetch('https://api.github.com/repos/dgonzalez13/esports-tracker-full/contents/tracked_players.txt?ref=main',
        {headers: {Accept: 'application/vnd.github+json'}, cache: 'no-store'})
    .then(response => response.ok ? response.json() : null)
    .then(file => {
      if (!file) return;
      const content = new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\s/g, '')), c => c.charCodeAt(0)));
      const excluded = content.split(/\r?\n/).filter(line => line.startsWith('@H2H_EXCLUDE||'))
        .map(line => { try { return JSON.parse(line.slice('@H2H_EXCLUDE||'.length)); } catch { return null; } });
      rows.forEach((row, index) => {
        const entry = entries[index];
        if (excluded.some(e => e && e.league === entry.league && e.group === entry.group &&
            e.player === entry.player && e.rival === entry.rival &&
            JSON.stringify([...e.members].sort()) === JSON.stringify([...entry.members].sort()))) row.remove();
      });
      section.querySelector('#h2h-hide-zero').dispatchEvent(new Event('change'));
    }).catch(() => {});
  dialog.querySelector('form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!active || submit.disabled) return;
    const target = active;
    const token = sessionToken || input.value.trim(); input.value = '';
    if (!token) return;
    submit.disabled = true;
    dialog.querySelector('.pair-cancel').disabled = true;
    disconnect.disabled = true;
    const headers = {Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`,
                     'X-GitHub-Api-Version': '2026-03-10'};
    const url = 'https://api.github.com/repos/dgonzalez13/esports-tracker-full/contents/tracked_players.txt';
    try {
      let saved = false;
      for (let attempt = 0; attempt < 3 && !saved; attempt++) {
        const read = await fetch(url + '?ref=main', {headers, cache: 'no-store'});
        if (!read.ok) {
          if (read.status === 401 || read.status === 403) sessionToken = '';
          throw new Error(`No se pudo leer el archivo (${read.status}). Comprueba el token y sus permisos.`);
        }
        const file = await read.json();
        const content = new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\s/g, '')), c => c.charCodeAt(0)));
        const members = content.split(/\r?\n/).map(line => line.trim())
          .filter(line => line.startsWith(target.entry.league + '|'))
          .slice((target.entry.group - 1) * 5, target.entry.group * 5)
          .map(line => line.split('|').slice(1).join('|').replace(/\*$/, '').trim()).sort();
        if (JSON.stringify(members) !== JSON.stringify([...target.entry.members].sort()))
          throw new Error('El grupo ha cambiado. Recarga la página antes de excluir la pareja.');
        const directive = '@H2H_EXCLUDE||' + JSON.stringify(target.entry);
        if (content.split(/\r?\n/).some(line => line.trim() === directive)) { saved = true; break; }
        const updated = content.replace(/\s*$/, '') + '\n' + directive + '\n';
        const encoded = btoa(Array.from(new TextEncoder().encode(updated), b => String.fromCharCode(b)).join(''));
        const write = await fetch(url, {method: 'PUT', headers: {...headers, 'Content-Type': 'application/json'},
          body: JSON.stringify({message: `Exclude highlighted H2H: ${target.entry.player} vs ${target.entry.rival}`,
                                branch: 'main', sha: file.sha, content: encoded})});
        if (write.status === 409) continue;
        if (!write.ok) {
          if (write.status === 401 || write.status === 403) sessionToken = '';
          throw new Error(`No se pudo guardar (${write.status}). La pareja sigue visible.`);
        }
        saved = true;
      }
      if (!saved) throw new Error('El archivo está cambiando. Vuelve a intentarlo.');
      sessionToken = token;
      target.row.remove();
      dialog.close();
      section.querySelector('#h2h-hide-zero').dispatchEvent(new Event('change'));
    } catch (error) {
      dialog.querySelector('.pair-error').textContent = error.message;
    } finally {
      submit.disabled = false;
      dialog.querySelector('.pair-cancel').disabled = false;
      disconnect.disabled = false;
      updateAuth();
    }
  });
})();
