import os
import sys
import time
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

def test_historia_usuario_8():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 8: TRANSICIONES Y TIEMPOS")
    print("=" * 70)

    init_db(force_reset=True)
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    tec_user, _ = UserModel.create_user("tec_pedro", "pedro@sistema.mx", "Clave123", "Pedro Técnico", "Responsable", "Activo")
    user_sol, _ = UserModel.create_user("sol_carlos", "carlos@sistema.mx", "Clave123", "Carlos Solicitante", "Usuario", "Activo")

    eq = EquipmentModel.get_active()[0]

    # Crear ticket inicial en estado Abierto
    ticket_a, _ = TicketModel.create_ticket(
        titulo="Falla en bomba de enfriamiento chiller",
        situacion_problema="Disparo por alta temperatura en circuito secundario.",
        detector_nombre="Operador Planta",
        equipo_id=eq["id"],
        categoria="Mecánica y Neumática",
        prioridad="Alta",
        solicitante_id=user_sol["id"],
        responsable_id=tec_user["id"]
    )
    assert ticket_a["estado"] == "Abierto"

    # [TEST 8.1] Rechazo de transiciones inválidas sin cambio de estado
    print("[TEST 8.1] Probando rechazo de transiciones inválidas (Abierto -> Cerrado)...")
    ok_inv, err_inv = TicketModel.update_status(ticket_a["id"], "Cerrado", admin_user, "Intento directo a cerrado")
    assert ok_inv is False, "No debe permitir saltar de Abierto a Cerrado directamente"
    assert "inválida" in err_inv.lower(), f"Mensaje incorrecto: {err_inv}"
    
    t_check = TicketModel.get_by_id(ticket_a["id"])
    assert t_check["estado"] == "Abierto", "El estado en la base de datos debe permanecer intacto"
    print(" -> PASÓ: Transición inválida rechazada sin alterar el estado del ticket.")

    # [TEST 8.2] Recorrido normal: Abierto -> En Proceso -> Resuelto -> Cerrado
    print("[TEST 8.2] Verificando recorrido normal de atención técnica...")
    # 1. Abierto -> En Proceso (Inicia atención)
    ok_proc, err_proc = TicketModel.update_status(ticket_a["id"], "En Proceso", tec_user, "Iniciando diagnóstico")
    assert ok_proc is True, f"Error al pasar a En Proceso: {err_proc}"
    t_proc = TicketModel.get_by_id(ticket_a["id"])
    assert t_proc["estado"] == "En Proceso"
    assert t_proc["fecha_inicio_atencion"] is not None, "Debe registrar fecha_inicio_atencion"

    # 2. En Proceso -> Resuelto (Técnico termina trabajo)
    ok_res, err_res = TicketModel.update_status(ticket_a["id"], "Resuelto", tec_user, "Sustitución de termostato completada con éxito.")
    assert ok_res is True, f"Error al pasar a Resuelto: {err_res}"
    t_res = TicketModel.get_by_id(ticket_a["id"])
    assert t_res["estado"] == "Resuelto"
    assert t_res["fecha_resolucion"] is not None, "Debe registrar fecha_resolucion"

    # 3. Resuelto -> Cerrado (Conformidad del solicitante)
    ok_cie, err_cie = TicketModel.update_status(ticket_a["id"], "Cerrado", user_sol, "Conforme con las pruebas realizadas.")
    assert ok_cie is True, f"Error al cerrar: {err_cie}"
    t_cie = TicketModel.get_by_id(ticket_a["id"])
    assert t_cie["estado"] == "Cerrado"
    assert t_cie["fecha_cierre"] is not None, "Debe registrar fecha_cierre"
    print(" -> PASÓ: Recorrido normal completado con registro de fechas y actores autorizados.")

    # [TEST 8.3] Recorrido con espera y motivo obligatorio
    print("[TEST 8.3] Probando transición a 'En Espera' y obligatoriedad de motivo...")
    ticket_b, _ = TicketModel.create_ticket(
        titulo="Reemplazo de servomotor J2",
        situacion_problema="Bobinado en corto.",
        detector_nombre="Inspector",
        equipo_id=eq["id"],
        categoria="Automatización Industrial",
        prioridad="Urgente",
        solicitante_id=user_sol["id"],
        responsable_id=tec_user["id"]
    )
    # Pasar a En Proceso
    TicketModel.update_status(ticket_b["id"], "En Proceso", tec_user, "Diagnóstico")

    # Intentar pasar a En Espera SIN motivo
    ok_esp_sin, err_esp_sin = TicketModel.update_status(ticket_b["id"], "En Espera", tec_user, "")
    assert ok_esp_sin is False, "Debe rechazar pasar a En Espera sin motivo"
    assert "motivo obligatorio de la espera" in err_esp_sin.lower()

    # Pasar a En Espera CON motivo justificado
    ok_esp_con, _ = TicketModel.update_status(ticket_b["id"], "En Espera", tec_user, "En espera de refacción: servomotor solicitado al proveedor Fanuc")
    assert ok_esp_con is True
    t_esp = TicketModel.get_by_id(ticket_b["id"])
    assert t_esp["estado"] == "En Espera"
    assert t_esp["motivo_espera"] is not None

    # Reanudar: En Espera -> En Proceso
    ok_reanudar, _ = TicketModel.update_status(ticket_b["id"], "En Proceso", tec_user, "Refacción recibida, reanudando montaje")
    assert ok_reanudar is True
    t_rean = TicketModel.get_by_id(ticket_b["id"])
    assert t_rean["estado"] == "En Proceso"
    assert "metricas_tiempo" in t_rean, "Debe calcular métricas de tiempo"
    print(" -> PASÓ: Recorrido con espera requiere motivo obligatorio y acumula tiempos de pausa.")

    # [TEST 8.4] Excepción de Cancelación justificada con motivo obligatorio
    print("[TEST 8.4] Verificando excepción de Cancelación justificada con motivo...")
    ticket_c, _ = TicketModel.create_ticket(
        titulo="Solicitud errónea por prueba",
        situacion_problema="Prueba de usuario.",
        detector_nombre="Carlos",
        equipo_id=eq["id"],
        categoria="Mantenimiento General",
        prioridad="Baja",
        solicitante_id=user_sol["id"]
    )
    # Intentar cancelar sin motivo
    ok_canc_sin, _ = TicketModel.update_status(ticket_c["id"], "Cancelado", user_sol, "")
    assert ok_canc_sin is False, "Debe rechazar cancelación sin motivo"

    # Cancelar con motivo
    ok_canc_con, _ = TicketModel.update_status(ticket_c["id"], "Cancelado", user_sol, "Cancelado por el solicitante: reporte duplicado por error de dedo.")
    assert ok_canc_con is True
    t_canc = TicketModel.get_by_id(ticket_c["id"])
    assert t_canc["estado"] == "Cancelado"
    assert t_canc["motivo_cancelacion"] is not None
    print(" -> PASÓ: Cancelación de ticket requiere justificación obligatoria.")

    # [TEST 8.5] Excepción de Duplicado relacionado
    print("[TEST 8.5] Verificando marcado de Duplicado con ticket relacionado y motivo...")
    ticket_d, _ = TicketModel.create_ticket(
        titulo="Reporte repetido del chiller",
        situacion_problema="Misma falla del ticket A.",
        detector_nombre="Operador Turno Tarde",
        equipo_id=eq["id"],
        categoria="Mecánica y Neumática",
        prioridad="Alta",
        solicitante_id=admin_user["id"]
    )
    # Marcar como Duplicado de ticket_a
    ok_dup, err_dup = TicketModel.update_status(
        ticket_id=ticket_d["id"],
        new_status="Duplicado",
        user=admin_user,
        comentario="Duplicado del ticket previo reportado en el turno matutino",
        ticket_relacionado_id=ticket_a["id"]
    )
    assert ok_dup is True, f"Error al marcar duplicado: {err_dup}"
    t_dup = TicketModel.get_by_id(ticket_d["id"])
    assert t_dup["estado"] == "Duplicado"
    assert t_dup["ticket_relacionado_id"] == ticket_a["id"]
    assert t_dup["ticket_relacionado_codigo"] == ticket_a["codigo"]
    print(" -> PASÓ: Ticket duplicado vinculado al ticket original con motivo inmutable.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 8 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_8()


