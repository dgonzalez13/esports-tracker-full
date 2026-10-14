(() => {
    const section = document.getElementById('active-repeat-matches');
    const select = section.querySelector('[data-repeat-grouping]');
    select.addEventListener('change', () => {
        for (const cell of section.querySelectorAll(':scope > .table-wrap td[data-original]')) {
            cell.textContent = cell.dataset[select.value];
        }
    });
})();
