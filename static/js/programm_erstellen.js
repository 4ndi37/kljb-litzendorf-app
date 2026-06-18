const WOCHENTAG_NAMEN = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

function isoZuWochentag(iso) {
    const d = new Date(iso + 'T00:00:00');
    const dd = iso.slice(8, 10);
    const mm = iso.slice(5, 7);
    return `${WOCHENTAG_NAMEN[d.getDay()]}, ${dd}.${mm}.`;
}

function updateTage(selectEl) {
    const tagSelect = document.getElementById('tag-select');
    const tage = EVENT_TAGE[selectEl.value] || [];
    tagSelect.innerHTML = '<option value="" disabled selected>-- Bitte wählen --</option>';
    tage.forEach(iso => {
        const opt = document.createElement('option');
        opt.value = iso;
        opt.textContent = isoZuWochentag(iso);
        tagSelect.appendChild(opt);
    });
    tagSelect.disabled = tage.length === 0;
}

function showSection(type) {
    document.getElementById('sec-spiel').style.display  = 'none';
    document.getElementById('sec-custom').style.display = 'none';
    document.getElementById('sec-info').style.display   = 'none';
    if (type === 'spiel')        document.getElementById('sec-spiel').style.display  = 'block';
    else if (type === 'custom')  document.getElementById('sec-custom').style.display = 'block';
    else                         document.getElementById('sec-info').style.display   = 'block';
}
