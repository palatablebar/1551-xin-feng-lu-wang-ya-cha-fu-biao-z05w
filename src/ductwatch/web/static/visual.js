function renderVisual(target, data) {
    const grid = node('div',undefined,'heat-grid');
    const sorted = [...data.rows].sort((a,b) => a.zone.localeCompare(b.zone,'zh') || a.key.localeCompare(b.key));
    for (const row of sorted) {
        const value = Math.round(100 * row.estimate);
        const tile = node('button',`${row.key} · ${value}`,'probe');
        tile.style.setProperty('--heat',`${value}%`);
        tile.style.setProperty('--tile-ink',value > 52 ? '#261d28' : '#fff0f9');
        tile.title = `${row.zone} ${row.state}`;
        tile.addEventListener('click',() => inspect(row));
        grid.append(tile);
    }
    const legend = node('div',undefined,'heat-key');
    legend.append(node('span','低偏离 0'),node('span','高偏离 100'));
    target.append(grid,legend);
}
