function initH2HGapFilters(sectionId) {
    const section = document.getElementById(sectionId);
    const controls = [...section.querySelectorAll('[data-gap-filters] input')];
    const rows = [...section.querySelectorAll(':scope > .table-wrap tbody tr')];
    const empty = section.querySelector('[data-gap-empty]');
    function update() {
        const selected = controls.find(control => control.checked);
        const minimum = selected ? Number(selected.value) : null;
        for (const row of rows) {
            const difference = Number(row.cells[4].textContent.trim());
            row.hidden = minimum !== null && (!Number.isFinite(difference) || difference < minimum);
        }
        empty.hidden = !rows.length || rows.some(row => !row.hidden);
    }
    for (const control of controls) {
        control.addEventListener('change', () => {
            if (control.checked) {
                for (const other of controls) {
                    if (other !== control) other.checked = false;
                }
            }
            update();
        });
    }
    update();
}
