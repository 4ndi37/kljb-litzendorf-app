function openDeleteModal(id) {
    document.getElementById('deleteForm').action = "/programm_punkt_loeschen/" + id;
    document.getElementById('deleteModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('deleteModal').style.display = 'none';
}

window.onclick = function(e) {
    const modal = document.getElementById('deleteModal');
    if (e.target === modal) closeModal();
}
