import io
import os
import sys
from pathlib import Path

# Inyectar paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

site_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for sp in site_candidates:
    if sp.is_dir() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))

from app import app
from database.db import init_db
from models.user import UserModel
from models.equipment import EquipmentModel
from models.ticket import TicketModel

def test_historia_usuario_5():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 5: REGISTRO CON EQUIPO")
    print("=" * 70)

    init_db(force_reset=True)
    client = app.test_client()

    # Iniciar sesión como Admin predeterminado (admin@sistema.mx / Admin123)
    client.post("/login", data={
        "identificador": "admin@sistema.mx",
        "password": "Admin123"
    }, follow_redirects=True)

    # Obtener un equipo activo
    equipo_activo = EquipmentModel.get_active()[0]
    
    # Obtener el equipo inactivo para pruebas de validación
    equipo_inactivo = EquipmentModel.get_by_codigo("EQ-OBS-007")
    assert equipo_inactivo["estado"] == "Inactivo", "EQ-OBS-007 debe estar Inactivo"

    # [TEST 5.1] Validación de campos obligatorios en formulario
    print("[TEST 5.1] Validando obligatoriedad de campos requeridos...")
    # Intento sin título
    resp_no_titulo = client.post("/tickets/nuevo", data={
        "titulo": "",
        "situacion_problema": "Descripción detallada del problema",
        "detector_nombre": "Operador",
        "equipo_id": str(equipo_activo["id"]),
        "prioridad": "Media"
    })
    assert resp_no_titulo.status_code == 400, "Debe rechazar solicitud sin título"

    # Intento sin situación
    resp_no_sit = client.post("/tickets/nuevo", data={
        "titulo": "Falla en motor",
        "situacion_problema": "",
        "detector_nombre": "Operador",
        "equipo_id": str(equipo_activo["id"]),
        "prioridad": "Media"
    })
    assert resp_no_sit.status_code == 400, "Debe rechazar solicitud sin situación"

    # Intento sin detector
    resp_no_det = client.post("/tickets/nuevo", data={
        "titulo": "Falla en motor",
        "situacion_problema": "Sobrecalentamiento excesivo",
        "detector_nombre": "",
        "equipo_id": str(equipo_activo["id"]),
        "prioridad": "Media"
    })
    assert resp_no_det.status_code == 400, "Debe rechazar solicitud sin nombre de detector"

    # Intento sin equipo
    resp_no_eq = client.post("/tickets/nuevo", data={
        "titulo": "Falla en motor",
        "situacion_problema": "Sobrecalentamiento excesivo",
        "detector_nombre": "Ing. Inspector",
        "equipo_id": "",
        "prioridad": "Media"
    })
    assert resp_no_eq.status_code == 400, "Debe rechazar solicitud sin equipo"
    print(" -> PASÓ: Todos los campos obligatorios fueron estrictamente validados.")

    # [TEST 5.2] Validación estricta de equipo activo (rechazo de equipo inactivo)
    print("[TEST 5.2] Intentando registrar solicitud con equipo inactivo (EQ-OBS-007)...")
    resp_inactivo = client.post("/tickets/nuevo", data={
        "titulo": "Intento de registro en equipo dado de baja",
        "situacion_problema": "Se intenta registrar mantenimiento en equipo inactivo",
        "detector_nombre": "Operador 3",
        "equipo_id": str(equipo_inactivo["id"]),
        "prioridad": "Baja"
    })
    assert resp_inactivo.status_code == 400, "Debe rechazar con 400 si el equipo no está Activo"
    assert "no puede ser seleccionado" in resp_inactivo.get_data(as_text=True) or "INACTIVO" in resp_inactivo.get_data(as_text=True)
    print(" -> PASÓ: Registro con equipo inactivo rechazado con mensaje descriptivo de seguridad.")

    # [TEST 5.3] Registro exitoso, generación de folio único y guardado de atributos
    print("[TEST 5.3] Registrando ticket válido con equipo activo y verificando folio único...")
    resp_ok = client.post("/tickets/nuevo", data={
        "titulo": "Alarma de sobrecarga en celda robótica",
        "situacion_problema": "El robot reporta código de paro E-12 al mover la pinza de agarre.",
        "detector_nombre": "Téc. Fernando Ruiz - Turno Vespertino",
        "equipo_id": str(equipo_activo["id"]),
        "categoria": "Automatización Industrial",
        "prioridad": "Alta",
        "ubicacion_equipo": "Nave Industrial 1 - Bahía A"
    }, follow_redirects=True)
    assert resp_ok.status_code == 200, "El ticket válido debe crearse exitosamente"
    html_text = resp_ok.get_data(as_text=True)
    assert "TK-2026-" in html_text, "Debe mostrar el folio único consecutivo generado"
    assert "Téc. Fernando Ruiz - Turno Vespertino" in html_text, "Debe mostrar el detector de la falla"
    print(" -> PASÓ: Solicitud registrada con folio único, solicitante, detector y equipo activo.")

    # [TEST 5.4] Registro con archivo de evidencia permitido (<= 10 MB)
    print("[TEST 5.4] Registrando solicitud con evidencia adjunta válida (<= 10 MB)...")
    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 2048)  # Archivo PNG de 2 KB
    resp_adjunto = client.post("/tickets/nuevo", data={
        "titulo": "Inspección fotográfica de fuga de aceite en compresor",
        "situacion_problema": "Goteo visible en retén frontal del cabezal de compresión.",
        "detector_nombre": "Supervisor de Servicios",
        "equipo_id": str(equipo_activo["id"]),
        "categoria": "Mecánica y Neumática",
        "prioridad": "Media",
        "evidencia": (fake_png, "evidencia_fuga_aceite.png")
    }, follow_redirects=True)
    assert resp_adjunto.status_code == 200, "Debe aceptar el ticket con evidencia"
    html_adj = resp_adjunto.get_data(as_text=True)
    assert "evidencia_fuga_aceite.png" in html_adj, "El nombre del archivo adjunto debe visualizarse en el ticket"
    assert "Descargar / Ver" in html_adj, "Debe mostrar botón de descarga de la evidencia"
    print(" -> PASÓ: Evidencia técnica <= 10 MB almacenada y vinculada en ticket_adjuntos.")

    # [TEST 5.5] Rechazo estricto de evidencia técnica que supere los 10 MB
    print("[TEST 5.5] Intentando adjuntar archivo de evidencia mayor a 10 MB (10.5 MB)...")
    oversized_data = io.BytesIO(b"X" * (10 * 1024 * 1024 + 500 * 1024))  # 10.5 MB
    resp_grande = client.post("/tickets/nuevo", data={
        "titulo": "Prueba de archivo excedido",
        "situacion_problema": "Intento de adjuntar archivo masivo de más de 10 MB",
        "detector_nombre": "Tester",
        "equipo_id": str(equipo_activo["id"]),
        "prioridad": "Baja",
        "evidencia": (oversized_data, "archivo_enorme.png")
    }, follow_redirects=True)
    # Debe ser rechazado (ya sea 413 o 400 por validación de tamaño)
    assert resp_grande.status_code in (400, 413), f"Se esperaba rechazo 400 o 413, obtenido {resp_grande.status_code}"
    print(" -> PASÓ: Archivo de evidencia que excede 10 MB fue rechazado estrictamente.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 5 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_5()


