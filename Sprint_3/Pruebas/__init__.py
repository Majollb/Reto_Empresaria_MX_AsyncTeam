"""Utilidades compartidas de limpieza para las suites de pruebas por Sprint."""
from config import UPLOAD_FOLDER
from database.db import init_db


def snapshot_uploads() -> set[str]:
    """Registra los nombres de archivos existentes en uploads/ antes de iniciar pruebas."""
    if not UPLOAD_FOLDER.exists():
        return set()
    return {p.name for p in UPLOAD_FOLDER.iterdir() if p.is_file()}


def restore_clean_state(initial_uploads: set[str] | None = None) -> None:
    """Restaura la BD dejando solo al Administrador y elimina adjuntos creados en pruebas."""
    init_db(force_reset=True)
    if not UPLOAD_FOLDER.exists():
        return
    keep = initial_uploads if initial_uploads is not None else set()
    for p in UPLOAD_FOLDER.iterdir():
        if p.is_file() and p.name not in keep:
            try:
                p.unlink()
            except OSError:
                pass
