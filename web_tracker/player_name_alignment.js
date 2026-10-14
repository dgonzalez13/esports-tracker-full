(() => {
    function alignNames(table) {
        const headers = [...table.querySelectorAll('thead tr:first-child th')];
        headers.forEach((header, index) => {
            if (!/^(player|players|opponent|jugador|rival|partido)(\s|$)/i.test(header.textContent.trim())) return;
            header.classList.add('player-name');
            for (const row of table.querySelectorAll('tbody tr')) {
                if (row.cells[index]) row.cells[index].classList.add('player-name');
            }
        });
    }
    document.querySelectorAll('table').forEach(alignNames);
    new MutationObserver(changes => {
        const tables = new Set();
        for (const change of changes) {
            if (change.target.nodeType === 1) {
                const table = change.target.closest('table');
                if (table) tables.add(table);
            }
            for (const node of change.addedNodes) {
                if (node.nodeType !== 1) continue;
                if (node.matches('table')) tables.add(node);
                node.querySelectorAll('table').forEach(table => tables.add(table));
            }
        }
        tables.forEach(alignNames);
    }).observe(document.body, {childList: true, subtree: true});
})();
