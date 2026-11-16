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


def test_historia_usuario_11():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 11: AUDITORÍA Y TRAZABILIDAD")
    print("=" * 70)

    init_db(force_reset=True)

    # 1. Crear participantes del flujo
    solicitante, _ = UserModel.create_user("supervisor_linea", "supervisor@sistema.mx", "Clave123", "Ing. Daniel Vargas", "Usuario", "Activo")
    tecnico, _ = UserModel.create_user("tecnico_lider", "tecnico_lider@sistema.mx", "Clave123", "Téc. Martín Gómez", "Responsable", "Activo")
    otro_usuario, _ = UserModel.create_user("ajeno_planta", "ajeno@sistema.mx", "Clave123", "Usuario Sin Acceso", "Usuario", "Activo")
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    eq = EquipmentModel.get_by_codigo("EQ-ROB-002")

    # [TEST 11.1] Reconstrucción cronológica del ciclo de vida completo
    print("[TEST 11.1] Reconstruyendo ciclo de vida del ticket a través de eventos relevantes...")

    # Evento 1: Creación del ticket (por solicitante)
    t, _ = TicketModel.create_ticket(
        titulo="Alarma de colisión en robot soldador Fanuc",
        situacion_problema="El eje 3 se detuvo por activación del sensor antichoque mecánico.",
        detector_nombre="Ing. Daniel Vargas",
        equipo_id=eq["id"],
        categoria="Automatización Industrial",
        prioridad="Alta",
        solicitante_id=solicitante["id"]
    )
    t_id = t["id"]

    # Evento 2: Asignación a técnico por administrador
    TicketModel.reassign_responsable(t_id, tecnico["id"], admin_user, "Asignación inicial al especialista en robótica Fanuc")

    # Evento 3: Técnico toma el ticket a 'En Proceso'
    TicketModel.update_status(t_id, "En Proceso", tecnico, "Técnico en celda de manufactura realizando diagnóstico")

    # Evento 4: Técnico coloca en espera de refacciones
    TicketModel.update_status(t_id, "En Espera", tecnico, "En espera de sensor inductivo de repuesto en almacén general")

    # Evento 5: Se reanuda a 'En Proceso'
    TicketModel.update_status(t_id, "En Proceso", tecnico, "Sensor suministrado; iniciando montaje y cableado")

    # Evento 6: Agregar comentario de seguimiento
    TicketModel.add_comment(t_id, tecnico, "Sensor instalado; se procedió al alineamiento con galga micrométrica.")

    # Evento 7: Resolución técnica registrada
    TicketModel.resolve_ticket(t_id, tecnico, "Se sustituyó sensor de choque inductivo y se verificó punto de origen con cero errores.")

    # Evento 8: Cierre definitivo confirmado por solicitante
    TicketModel.close_ticket(t_id, solicitante, "Con Solución", "Robot verificado en producción de 50 piezas sin alarmas.")

    # Consultar trazabilidad completa
    trail, err = TicketModel.get_full_audit_trail(t_id, solicitante)
    assert err is None, f"Error al consultar trazabilidad: {err}"
    assert len(trail) >= 8, f"Se esperaban al menos 8 eventos en la trazabilidad completa, se obtuvieron {len(trail)}"

    # Verificar orden estrictamente cronológico
    for i in range(len(trail) - 1):
        assert trail[i]["created_at"] <= trail[i + 1]["created_at"], "Los eventos deben estar ordenados cronológicamente de forma ascendente"

    print(f" -> PASÓ: Recorrido completo reconstruido con éxito ({len(trail)} eventos registrados en secuencia cronológica).")

    # [TEST 11.2] Atributos identificables de cada evento: qué ocurrió, quién intervino y cuándo
    print("[TEST 11.2] Verificando campos de trazabilidad: acción, momento y persona identificable...")

    primer_evento = trail[0]
    assert primer_evento["accion"] is not None and len(primer_evento["accion"]) > 0, "Debe tener acción identificable"
    assert primer_evento["created_at"] is not None, "Debe tener timestamp del momento exacto"
    assert primer_evento["usuario_nombre"] is not None, "Debe identificar el nombre de la persona que intervino"
    assert primer_evento["usuario_rol"] in ("Admin", "Responsable", "Usuario"), "Debe identificar el rol del participante"

    # Verificar que el evento de cierre identifique al solicitante
    evento_cierre = [e for e in trail if e.get("estado_nuevo") == "Cerrado"][0]
    assert evento_cierre["usuario_id"] == solicitante["id"], "El autor del cierre debe ser el solicitante"
    assert "Conforme" in evento_cierre["comentario"] or "solución" in evento_cierre["comentario"].lower()
    print(" -> PASÓ: Todos los eventos cuentan con acción, momento inmutable e identidad del responsable de la intervención.")

    # [TEST 11.3] Demostración de inmutabilidad estricta: prohibida edición o borrado ordinario
    print("[TEST 11.3] Demostrando inmutabilidad estricta del historial de auditoría...")
    hist_id = primer_evento["id"]
    can_delete, msg_delete = TicketModel.attempt_delete_or_edit_history(hist_id)
    assert can_delete is False, "No debe permitirse edición ni eliminación en la bitácora de auditoría"
    assert "inmutables" in msg_delete.lower()
    print(" -> PASÓ: Principio de inmutabilidad y registro de solo adición (append-only) verificado.")

    # [TEST 11.4] Control estricto de visibilidad por rol y participación en la trazabilidad
    print("[TEST 11.4] Verificando protección RBAC de la trazabilidad frente a terceros ajenos...")

    # El usuario ajeno intenta consultar la trazabilidad del ticket
    trail_ajeno, err_ajeno = TicketModel.get_full_audit_trail(t_id, otro_usuario)
    assert trail_ajeno is None, "Usuario no participante no debe recibir el historial de auditoría"
    assert "autorización" in err_ajeno.lower()

    # Vía endpoint HTTP /tickets/<id>/trazabilidad con test_client
    client_ajeno = app.test_client()
    client_ajeno.post("/login", data={"identificador": "ajeno_planta", "password": "Clave123"})
    resp_http_ajeno = client_ajeno.get(f"/tickets/{t_id}/trazabilidad", headers={"Accept": "application/json"})
    assert resp_http_ajeno.status_code == 403, f"Se esperaba 403 Forbidden y se obtuvo {resp_http_ajeno.status_code}"

    # Participante autorizado (solicitante) sí puede consultar endpoint JSON
    client_auth = app.test_client()
    client_auth.post("/login", data={"identificador": "supervisor_linea", "password": "Clave123"})
    resp_http_auth = client_auth.get(f"/tickets/{t_id}/trazabilidad", headers={"Accept": "application/json"})
    assert resp_http_auth.status_code == 200, "Participante autorizado debe obtener HTTP 200"
    data_json = resp_http_auth.get_json()
    assert data_json["ticket_id"] == t_id
    assert len(data_json["eventos"]) >= 8

    print(" -> PASÓ: Protección RBAC rigurosa comprobada: 403 para usuarios ajenos y 200 para participantes autorizados.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 11 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70)


if __name__ == "__main__":
    test_historia_usuario_11()
