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


def test_historia_usuario_10():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 10: CIERRE Y RECURRENCIA")
    print("=" * 70)

    init_db(force_reset=True)

    # 1. Crear usuarios de prueba
    solicitante, _ = UserModel.create_user("operador_planta", "operador@sistema.mx", "Clave123", "Ing. Roberto Solís", "Usuario", "Activo")
    tecnico, _ = UserModel.create_user("tecnico_mant", "tecnico@sistema.mx", "Clave123", "Téc. Fernando Ruiz", "Responsable", "Activo")
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    eq = EquipmentModel.get_by_codigo("EQ-PLC-001")

    # 2. Crear ticket base para resolución y cierre
    ticket, err = TicketModel.create_ticket(
        titulo="Falla intermitente en servomotor eje Y",
        situacion_problema="El servomotor presenta sobrecorriente aleatoria en rampa de aceleración.",
        detector_nombre="Ing. Roberto Solís",
        equipo_id=eq["id"],
        categoria="Mantenimiento Correctivo",
        prioridad="Alta",
        solicitante_id=solicitante["id"],
        responsable_id=tecnico["id"]
    )
    assert ticket is not None, f"Error al crear ticket: {err}"
    t_id = ticket["id"]

    # Pasar ticket a En Proceso
    ok_proc, err_proc = TicketModel.update_status(t_id, "En Proceso", tecnico, "Iniciando diagnóstico con osciloscopio.")
    assert ok_proc is True, f"Fallo al pasar a En Proceso: {err_proc}"

    # [TEST 10.1] Registro de Resolución Técnica obligatoria y validaciones
    print("[TEST 10.1] Registrando resolución técnica y validando reglas de negocio...")

    # Rechazar si la solución está vacía o es muy corta (< 8 caracteres)
    ok_bad, err_bad = TicketModel.resolve_ticket(t_id, tecnico, "ok")
    assert ok_bad is False, "Debe rechazar solución demasiado breve o vacía"
    assert "mínimo 8 caracteres" in err_bad

    # Rechazar si un usuario no asignado ni admin intenta resolver
    ok_unauth, err_unauth = TicketModel.resolve_ticket(t_id, solicitante, "Se cambió el fusible pero no tengo permiso")
    assert ok_unauth is False, "Usuario solicitante no debe poder resolver técnicamente el ticket"

    # Resolución válida por el técnico asignado
    solucion_valida = "Se calibró el lazo de corriente del servodrive y se reemplazó el conector de potencia desajustado."
    ok_res, err_res = TicketModel.resolve_ticket(t_id, tecnico, solucion_valida)
    assert ok_res is True, f"Error al registrar resolución válida: {err_res}"

    t_resuelto = TicketModel.get_by_id(t_id)
    assert t_resuelto["estado"] == "Resuelto", "El estado debe cambiar a Resuelto"
    assert t_resuelto["solucion_detalle"] == solucion_valida, "La solución técnica debe quedar registrada"
    assert t_resuelto["fecha_resolucion"] is not None, "Debe registrarse timestamp de resolución"
    print(" -> PASÓ: Resolución técnica registrada con éxito, solución detallada y timestamp inmutable.")

    # [TEST 10.2] Confirmación de Cierre Definitivo 'Con Solución' por solicitante o admin
    print("[TEST 10.2] Confirmando cierre definitivo con solución satisfactoria...")
    ok_close, err_close = TicketModel.close_ticket(t_id, solicitante, "Con Solución", "Conforme con las pruebas en vacío y bajo carga.")
    assert ok_close is True, f"Error al cerrar ticket: {err_close}"

    t_cerrado = TicketModel.get_by_id(t_id)
    assert t_cerrado["estado"] == "Cerrado", "El estado debe ser Cerrado"
    assert t_cerrado["tipo_cierre"] == "Con Solución", "Tipo de cierre debe ser Con Solución"
    assert t_cerrado["fecha_cierre"] is not None, "Debe guardarse timestamp de cierre"
    print(" -> PASÓ: Cierre confirmado por solicitante, tipo de cierre 'Con Solución' registrado.")

    # [TEST 10.3] Inmutabilidad estricta tras cierre: bloqueo de cambios ordinarios
    print("[TEST 10.3] Verificando bloqueo estricto contra modificaciones ordinarias tras cierre...")

    # Intento 1: Cambiar estado en ticket cerrado
    ok_st, err_st = TicketModel.update_status(t_id, "En Proceso", admin_user, "Intentando reabrir")
    assert ok_st is False, "No debe permitir actualizar estado ordinariamente de un ticket Cerrado"
    assert "bloqueado contra modificaciones ordinarias" in err_st

    # Intento 2: Reasignar responsable en ticket cerrado
    ok_reass, err_reass = TicketModel.reassign_responsable(t_id, admin_user["id"], admin_user, "Cambio tardío")
    assert ok_reass is False, "No debe permitir reasignar un ticket Cerrado"
    assert "se encuentra Cerrado" in err_reass

    # Intento 3: Agregar comentarios en ticket cerrado
    ok_comm, err_comm = TicketModel.add_comment(t_id, admin_user, "Comentario extemporáneo")
    assert not ok_comm, "No debe permitir nuevos comentarios ordinarios en ticket Cerrado"
    assert "se encuentra Cerrado" in err_comm

    print(" -> PASÓ: Inmutabilidad garantizada; todo intento de cambio ordinario sobre ticket cerrado es bloqueado.")

    # [TEST 10.4] Cierre 'Sin Solución' justificado conservando diagnósticos previos
    print("[TEST 10.4] Verificando caso de cierre sin solución con justificación obligatoria...")
    t2, _ = TicketModel.create_ticket(
        titulo="Falla en tarjeta electrónica CNC descartada por obsolescencia",
        situacion_problema="Componentes quemados en PCB de control año 1994.",
        detector_nombre="Ing. Roberto Solís",
        equipo_id=eq["id"],
        categoria="Mantenimiento Correctivo",
        prioridad="Media",
        solicitante_id=solicitante["id"],
        responsable_id=tecnico["id"]
    )
    # Agregar un comentario de diagnóstico previo
    TicketModel.add_comment(t2["id"], tecnico, "Se revisó diagrama y no existen repuestos en el mercado.")

    # Intento de cierre sin solución sin motivo -> Rechazar
    ok_no_mot, err_no_mot = TicketModel.close_ticket(t2["id"], admin_user, "Sin Solución", "")
    assert ok_no_mot is False, "Debe rechazar cierre sin solución si no hay justificación obligatoria"
    assert "obligatoriamente la justificación" in err_no_mot

    # Cierre sin solución válido
    motivo_justif = "El fabricante descontinuó la tarjeta hace 20 años; no es técnicamente viable reparar. Se gestionará reemplazo del equipo completo."
    ok_cerr_sin, err_cerr_sin = TicketModel.close_ticket(t2["id"], admin_user, "Sin Solución", motivo_justif)
    assert ok_cerr_sin is True, f"Error al cerrar sin solución: {err_cerr_sin}"

    t2_verif = TicketModel.get_by_id(t2["id"])
    assert t2_verif["estado"] == "Cerrado"
    assert t2_verif["tipo_cierre"] == "Sin Solución"
    assert t2_verif["motivo_sin_solucion"] == motivo_justif
    # Comprobar que los comentarios previos siguen intactos
    comments_t2 = [h for h in TicketModel.get_history(t2["id"]) if "Comentario" in h.get("accion", "")]
    assert len(comments_t2) >= 1, "Debe conservar los comentarios y diagnósticos previos"
    assert any("no existen repuestos" in (c.get("comentario") or c.get("motivo_detalle") or "") for c in comments_t2)
    print(" -> PASÓ: Cierre sin solución registrado exitosamente conservando diagnósticos y motivos obligatorios.")

    # [TEST 10.5] Reportar recurrencia: nueva atención relacionada vinculada bidireccionalmente
    print("[TEST 10.5] Creando nueva atención por recurrencia sobre ticket cerrado...")

    # Intento de recurrencia sin descripción suficiente (< 8 caracteres)
    rec_bad, err_rec_bad = TicketModel.create_recurrence(t_id, solicitante, "falla")
    assert rec_bad is None, "Debe rechazar recurrencia sin descripción adecuada"

    # Recurrencia válida
    desc_recurrencia = "El eje Y volvió a disparar sobrecorriente al superar las 2,000 RPM durante el turno matutino."
    nueva_atencion, err_rec = TicketModel.create_recurrence(
        ticket_id=t_id,
        user=solicitante,
        situacion_falla=desc_recurrencia,
        prioridad="Urgente"
    )
    assert nueva_atencion is not None, f"Error al crear recurrencia: {err_rec}"
    assert nueva_atencion["id"] != t_id, "Debe ser un nuevo ticket con ID independiente"
    assert nueva_atencion["codigo"] != t_cerrado["codigo"], "Debe tener nuevo folio único correlativo"
    assert nueva_atencion["estado"] == "Abierto", "La nueva atención debe iniciar en Abierto"
    assert nueva_atencion["prioridad"] == "Urgente", "Debe admitir prioridad de recurrencia"

    # Verificar vinculación en base de datos
    t_nuevo_db = TicketModel.get_by_id(nueva_atencion["id"])
    assert t_nuevo_db["es_recurrencia"] == 1, "Debe estar marcado con la bandera es_recurrencia"
    assert t_nuevo_db["ticket_origen_recurrencia_id"] == t_id, "Debe apuntar al ticket origen"
    assert t_nuevo_db["ticket_relacionado_id"] == t_id, "Debe vincularse con ticket_relacionado_id"
    assert t_nuevo_db["tipo_relacion"] == "Recurrencia", "tipo_relacion debe ser 'Recurrencia'"

    # Verificar que el ticket origen liste la recurrencia hija
    t_origen_db = TicketModel.get_by_id(t_id)
    assert any(h["id"] == nueva_atencion["id"] for h in t_origen_db.get("tickets_recurrentes", [])), "El ticket origen debe listar la recurrencia generada"

    print(" -> PASÓ: Nueva atención relacionada por recurrencia creada y vinculada bidireccionalmente.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 10 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70)


if __name__ == "__main__":
    test_historia_usuario_10()
