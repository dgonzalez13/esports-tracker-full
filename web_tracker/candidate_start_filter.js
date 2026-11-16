(() => {
  document.querySelectorAll('#bet-candidates .candidate-horizon').forEach(block => {
    const checkbox = block.querySelector('.hide-first-match');
    const rows = [...block.querySelectorAll('.candidate-entry')];
    const empty = block.querySelector('.candidate-filter-empty');
    const update = () => {
      rows.forEach(row => { row.hidden = checkbox.checked && row.dataset.firstMatch === 'true'; });
      empty.hidden = !rows.length || rows.some(row => !row.hidden);
    };
    checkbox.addEventListener('change', update);
    update();
  });
})();
