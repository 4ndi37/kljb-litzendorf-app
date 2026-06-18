let aufgabenSpeicher = [];

function _renderPreview() {
    const vorschauDiv = document.getElementById('aufgaben-vorschau');
    const listeUl     = document.getElementById('aufgaben-liste');
    if (!vorschauDiv || !listeUl) return;
    listeUl.innerHTML = '';
    if (aufgabenSpeicher.length === 0) { vorschauDiv.style.display = 'none'; return; }
    vorschauDiv.style.display = 'block';
    const ld = window._leiterData || {};
    aufgabenSpeicher.forEach(function(aufg, idx) {
        const namen = aufg.leiter_ids.map(function(id) { return ld[id] || String(id); });
        const li  = document.createElement('li');
        li.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:4px;';
        const b   = document.createElement('b');
        b.textContent = aufg.text;
        const txt = document.createTextNode(' → ' + namen.join(', '));
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ms-chip-remove';
        btn.textContent = '×';
        btn.setAttribute('aria-label', 'Aufgabe entfernen');
        btn.addEventListener('click', (function(i) {
            return function() {
                aufgabenSpeicher.splice(i, 1);
                document.getElementById('aufgaben_json').value = JSON.stringify(aufgabenSpeicher);
                _renderPreview();
            };
        })(idx));
        li.appendChild(b);
        li.appendChild(txt);
        li.appendChild(btn);
        listeUl.appendChild(li);
    });
}

function fuegeAufgabeHinzu() {
    const textInput = document.getElementById('temp_aufgabe_text');
    const text = textInput.value.trim();
    const ids   = window.leiterMs ? window.leiterMs.getSelectedIds()   : [];

    if (text === '' || ids.length === 0) {
        alert('Bitte einen Aufgabentext eingeben und mindestens eine Person auswählen!');
        return;
    }

    aufgabenSpeicher.push({ text: text, leiter_ids: ids });
    document.getElementById('aufgaben_json').value = JSON.stringify(aufgabenSpeicher);
    _renderPreview();
    textInput.value = '';
    window.leiterMs.clearSelection();
}

function initAufgaben(existing) {
    aufgabenSpeicher = existing;
    document.getElementById('aufgaben_json').value = JSON.stringify(aufgabenSpeicher);
    _renderPreview();
}
