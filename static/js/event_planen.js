function toggleBemerkung(wert) {
    const container = document.getElementById('bemerkung_container');
    const inputFeld = document.getElementById('bemerkung_input');
    if (wert === 'teilweise') {
        container.style.display = 'block';
        inputFeld.required = true;
    } else {
        container.style.display = 'none';
        inputFeld.required = false;
    }
}
