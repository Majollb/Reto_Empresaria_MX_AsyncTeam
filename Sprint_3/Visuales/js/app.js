// JavaScript interactivo para Automatización y Software del Bajío

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('active');
}

// Cargar datos en el modal de edición de usuario
function prepareEditUserModal(user) {
  document.getElementById('edit_user_id').value = user.id;
  document.getElementById('edit_nombre_completo').value = user.nombre_completo;
  document.getElementById('edit_username').value = user.username;
  document.getElementById('edit_email').value = user.email;
  document.getElementById('edit_rol').value = user.rol;
  document.getElementById('edit_estado').value = user.estado;
  document.getElementById('edit_form').action = `/admin/usuarios/${user.id}/editar`;
  openModal('modal-edit-user');
}

// Confirmación para alternar estado de usuario
function confirmToggleStatus(username, currentStatus) {
  const next = currentStatus === 'Activo' ? 'desactivar' : 'activar';
  return confirm(`¿Está seguro que desea ${next} la cuenta del usuario "${username}"?`);
}

// Cerrar modales con Escape o clic fuera
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
  }
});

document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
  }
});

