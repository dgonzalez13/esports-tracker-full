(() => {
  const section = document.getElementById('first-win-window-candidates');
  const checkbox = document.getElementById('repeat-show-small-samples');
  const update = () => {
    section.querySelectorAll('.repeat-low-sample').forEach(row => { row.hidden = !checkbox.checked; });
    const rows = [...section.querySelectorAll('.candidate-list > span')];
    document.getElementById('repeat-candidates-empty').hidden = !rows.length || rows.some(row => !row.hidden);
  };
  checkbox.addEventListener('change', update);
  update();
})();
