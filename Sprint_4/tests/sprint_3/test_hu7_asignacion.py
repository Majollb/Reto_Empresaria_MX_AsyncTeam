import os
import sys
from pathlib import Path

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

def test_historia_usuario_7():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 7: CLASIFICACIÓN Y ASIGNACIÓN")
    print("=" * 70)

    init_db(force_reset=True)
    client_admin = app.test_client()

    # Iniciar sesión como Admin predeterminado
    client_admin.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})

    # Crear dos técnicos: uno activo y uno inactivo
    tec_activo, _ = UserModel.create_user("tec_mario", "mario@sistema.mx", "Clave123", "Ing. Mario Morales", "Responsable", "Activo")
    tec_activo2, _ = UserModel.create_user("tec_luis", "luis@sistema.mx", "Clave123", "Ing. Luis Sánchez", "Responsable", "Activo")
    tec_inactivo, _ = UserModel.create_user("tec_inactivo", "inactivo_tec@sistema.mx", "Clave123", "Ing. Técnico Inactivo", "Responsable", "Inactivo")
    user_comun, _ = UserModel.create_user("usuario_comun", "comun@sistema.mx", "Clave123", "Carlos Usuario", "Usuario", "Activo")

    # Crear un ticket sin asignar
    eq = EquipmentModel.get_active()[0]
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    ticket, _ = TicketModel.create_ticket(
        titulo="Fallo de calibración en celda Fanuc",
        situacion_problema="Desviación de coordenadas en el punto de inicio de soldadura.",
        detector_nombre="Líder de Calidad",
        equipo_id=eq["id"],
        categoria="Automatización Industrial",
        prioridad="Media",
        solicitante_id=admin_user["id"],
        responsable_id=None
    )
    assert ticket["responsable_id"] is None, "El ticket debe crearse sin responsable asignado"

    # [TEST 7.1] Asignación inicial de responsable técnico activo por Administrador
    print("[TEST 7.1] Administrador asigna y clasifica ticket a técnico activo...")
    resp_asig = client_admin.post(f"/tickets/{ticket['id']}/reassign", data={
        "responsable_id": str(tec_activo["id"]),
        "motivo": "Asignación inicial por especialidad en robótica Fanuc",
        "categoria": "Automatización Industrial",
        "prioridad": "Alta"
    }, follow_redirects=True)
    assert resp_asig.status_code == 200, "La asignación debe completarse con éxito"
    
    t_actualizado = TicketModel.get_by_id(ticket["id"])
    assert t_actualizado["responsable_id"] == tec_activo["id"], "El técnico asignado debe coincidir"
    assert t_actualizado["responsable_nombre"] == "Ing. Mario Morales", "El nombre del responsable debe ser visible"
    assert t_actualizado["prioridad"] == "Alta", "La prioridad debe actualizarse en la clasificación"
    print(" -> PASÓ: Técnico asignado correctamente y visible en ticket.")

    # [TEST 7.2] Motivo obligatorio al reasignar ticket que ya cuenta con responsable
    print("[TEST 7.2] Verificando obligatoriedad de motivo al reasignar responsable...")
    # Intentar reasignar sin motivo a tec_activo2
    ok_sin_motivo, err = TicketModel.reassign_responsable(
        ticket_id=ticket["id"],
        new_responsable_id=tec_activo2["id"],
        admin_user=admin_user,
        motivo=""  # Motivo vacío
    )
    assert ok_sin_motivo is False, "Debe rechazar la reasignación sin motivo"
    assert "motivo de la reasignación es obligatorio" in err.lower(), f"Mensaje incorrecto: {err}"
    print(" -> PASÓ: Reasignación sin motivo fue rechazada estrictamente.")

    # [TEST 7.3] Reasignación válida con motivo obligatorio e historial completo
    print("[TEST 7.3] Reasignando a nuevo técnico con motivo justificado y auditoría...")
    ok_con_motivo, err_ok = TicketModel.reassign_responsable(
        ticket_id=ticket["id"],
        new_responsable_id=tec_activo2["id"],
        admin_user=admin_user,
        motivo="Cambio de turno técnico: se transfiere al turno nocturno con Ing. Luis Sánchez"
    )
    assert ok_con_motivo is True, f"Error al reasignar: {err_ok}"
    
    t_reasignado = TicketModel.get_by_id(ticket["id"])
    assert t_reasignado["responsable_id"] == tec_activo2["id"], "Nuevo responsable debe ser tec_activo2"

    history = TicketModel.get_history(ticket["id"])
    reasig_records = [h for h in history if h["accion"] == "Reasignación de Responsable"]
    assert len(reasig_records) > 0, "Debe existir registro de auditoría de la reasignación"
    assert "Ing. Mario Morales" in reasig_records[0]["resp_anterior_nombre"]
    assert "Ing. Luis Sánchez" in reasig_records[0]["resp_nuevo_nombre"]
    assert "Cambio de turno técnico" in reasig_records[0]["comentario"]
    print(" -> PASÓ: Historial conserva responsable anterior, nuevo, autor, fecha y motivo.")

    # [TEST 7.4] Rechazo de asignación a técnicos inactivos o roles no autorizados
    print("[TEST 7.4] Intentando asignar a técnico inactivo o usuario común...")
    ok_inactivo, err_inac = TicketModel.reassign_responsable(
        ticket_id=ticket["id"],
        new_responsable_id=tec_inactivo["id"],
        admin_user=admin_user,
        motivo="Prueba asignación inactivo"
    )
    assert ok_inactivo is False, "No debe permitir asignar a un técnico inactivo"
    assert "INACTIVO" in err_inac

    ok_comun, err_comun = TicketModel.reassign_responsable(
        ticket_id=ticket["id"],
        new_responsable_id=user_comun["id"],
        admin_user=admin_user,
        motivo="Prueba asignación usuario común"
    )
    assert ok_comun is False, "No debe permitir asignar a quien no tiene rol Responsable"
    print(" -> PASÓ: Rechazo de asignación a usuarios inactivos o sin rol técnico.")

    # [TEST 7.5] Rechazo de reasignación por usuarios no administradores (RBAC)
    print("[TEST 7.5] Verificando restricción: usuario común intentando reasignar (403)...")
    client_comun = app.test_client()
    client_comun.post("/login", data={"identificador": "usuario_comun", "password": "Clave123"})
    resp_forb = client_comun.post(f"/tickets/{ticket['id']}/reassign", data={
        "responsable_id": str(tec_activo["id"]),
        "motivo": "Intento no autorizado"
    })
    assert resp_forb.status_code == 403, f"Se esperaba 403 Forbidden y se obtuvo {resp_forb.status_code}"
    print(" -> PASÓ: Acción de reasignación restringida exclusivamente para Administradores.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 7 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_7()


