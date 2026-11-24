(() => {
  const section = document.getElementById('daily-pair-watch');
  const data = document.getElementById('daily-pair-watch-data');
  if (!section || !data) return;
  const metadata = JSON.parse(data.textContent);
  const rows = [...section.querySelectorAll('tbody tr')];
  const hour = new Intl.DateTimeFormat('en-GB', {timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'});
  function update() {
    const now = Date.now(), cutoff = now - 15 * 60000, windowStart = now - 8 * 3600000;
    const ranked = [];
    rows.forEach((row, index) => {
      const item = metadata[index];
      const eligible = item.fixtures.filter(f => Date.parse(f.timestamp) > cutoff)
        .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
      row.hidden = !eligible.length;
      if (row.hidden) return;
      const sequence = (item.fallback_sequence || '') + [...item.events]
        .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
        .filter(e => Date.parse(e.timestamp) <= now && Date.parse(e.timestamp) >= windowStart)
        .map(e => e.result || (Date.parse(e.timestamp) <= cutoff ? '?' : '')).join('');
      row.cells[5].textContent = sequence || 'Sin resultados (8 h)';
      row.cells[6].textContent = hour.format(Date.parse(eligible[0].timestamp)) + (eligible[0].estimated ? ' (estimado)' : '');
      row.classList.toggle('daily-pair-pending', sequence.includes('?'));
      row.classList.toggle('daily-pair-green', !sequence.includes('?') && !sequence.endsWith('V'));
      ranked.push([Date.parse(eligible[0].timestamp), row]);
    });
    ranked.sort((a, b) => a[0] - b[0]).forEach(([, row]) => row.parentNode.appendChild(row));
  }
  update();
  setInterval(update, 30000);
  document.addEventListener('visibilitychange', update);
})();
