function zutatHinzufuegen() {
    const container = document.getElementById('zutaten-container');
    const zeile = document.createElement('div');
    zeile.className = 'zutat-zeile form-row';
    zeile.style.marginBottom = '8px';
    zeile.innerHTML = `
        <input type="text"   name="zutat_name"    placeholder="Zutat" required>
        <input type="number" name="zutat_menge"   placeholder="Menge" step="0.1" required>
        <input type="text"   name="zutat_einheit" placeholder="g / ml / Stück" required style="max-width:120px;">
    `;
    container.appendChild(zeile);
}
