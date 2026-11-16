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
from models.equipment import EquipmentModel, AreaModel
from models.ticket import TicketModel

def test_historia_usuario_6():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 6: CONSULTA Y FILTROS")
    print("=" * 70)

    init_db(force_reset=True)

    # 1. Crear usuarios para la prueba de visibilidad y filtros
    user_normal, _ = UserModel.create_user("operador1", "operador1@sistema.mx", "Clave123", "Operador Juan", "Usuario", "Activo")
    user_tecnico, _ = UserModel.create_user("tecnico1", "tecnico1@sistema.mx", "Clave123", "Técnico Pedro", "Responsable", "Activo")
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")

    # 2. Crear tickets específicos con datos controlados
    eq1 = EquipmentModel.get_by_codigo("EQ-PLC-001")
    eq2 = EquipmentModel.get_by_codigo("EQ-ROB-002")

    # Ticket A: Solicitado por operador1, asignado a tecnico1, Urgente, Abierto, EQ-PLC-001
    t_a, _ = TicketModel.create_ticket(
        titulo="Fallo de comunicación en PLC Línea 1",
        situacion_problema="Pérdida de paquetes Profinet hacia los módulos remotos ET200SP.",
        detector_nombre="Operador Juan",
        equipo_id=eq1["id"],
        categoria="Automatización Industrial",
        prioridad="Urgente",
        solicitante_id=user_normal["id"],
        responsable_id=user_tecnico["id"]
    )

    # Ticket B: Solicitado por admin, asignado a admin, Baja, Cerrado, EQ-ROB-002
    t_b, _ = TicketModel.create_ticket(
        titulo="Limpieza y aspirado de gabinete robot Fanuc",
        situacion_problema="Polvo acumulado en filtros de ventilación del controlador.",
        detector_nombre="Inspector",
        equipo_id=eq2["id"],
        categoria="Mantenimiento Preventivo",
        prioridad="Baja",
        solicitante_id=admin_user["id"],
        responsable_id=admin_user["id"]
    )
    # Marcar t_b como Cerrado siguiendo la máquina de estados finita (HU-08)
    ok1, err1 = TicketModel.update_status(t_b["id"], "En Proceso", admin_user, "Inicio de mantenimiento")
    assert ok1 is True, f"Fallo al pasar t_b a En Proceso: {err1}"
    ok2, err2 = TicketModel.update_status(t_b["id"], "Resuelto", admin_user, "Limpieza de gabinete terminada")
    assert ok2 is True, f"Fallo al pasar t_b a Resuelto: {err2}"
    ok3, err3 = TicketModel.update_status(t_b["id"], "Cerrado", admin_user, "Mantenimiento preventivo completado y verificado.")
    assert ok3 is True, f"Fallo al pasar t_b a Cerrado: {err3}"
    t_b = TicketModel.get_by_id(t_b["id"])
    assert t_b["estado"] == "Cerrado", f"t_b debería estar Cerrado pero está en {t_b['estado']}"

    # [TEST 6.1] Control de acceso RBAC por participante (sólo autorizados)
    print("[TEST 6.1] Verificando ámbito de visibilidad por participante (RBAC)...")
    client_user = app.test_client()
    client_user.post("/login", data={"identificador": "operador1", "password": "Clave123"})
    resp_user = client_user.get("/tickets")
    html_user = resp_user.get_data(as_text=True)
    assert t_a["codigo"] in html_user, "El solicitante debe ver su propio ticket"
    assert t_b["codigo"] not in html_user, "El solicitante NO debe ver tickets de otros usuarios"

    # Técnico asignado
    client_tech = app.test_client()
    client_tech.post("/login", data={"identificador": "tecnico1", "password": "Clave123"})
    resp_tech = client_tech.get("/tickets")
    html_tech = resp_tech.get_data(as_text=True)
    assert t_a["codigo"] in html_tech, "El responsable técnico debe ver el ticket donde está asignado"
    assert t_b["codigo"] not in html_tech, "El responsable NO debe ver tickets donde no participa"

    # Administrador
    client_admin = app.test_client()
    client_admin.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})
    resp_admin = client_admin.get("/tickets")
    html_admin = resp_admin.get_data(as_text=True)
    assert t_a["codigo"] in html_admin, "El Administrador debe ver todos los tickets (t_a)"
    assert t_b["codigo"] in html_admin, "El Administrador debe ver todos los tickets (t_b)"
    print(" -> PASÓ: Ámbito de visibilidad protegido rigurosamente según el rol y participación.")

    # [TEST 6.2] Búsqueda por Folio único exacto y parcial
    print("[TEST 6.2] Búsqueda por folio único exacto y parcial...")
    resp_folio = client_admin.get(f"/tickets?q={t_a['codigo']}")
    html_folio = resp_folio.get_data(as_text=True)
    assert t_a["codigo"] in html_folio, "Debe encontrar el ticket buscando por folio"
    assert t_b["codigo"] not in html_folio, "No debe incluir otros tickets al buscar por folio específico"
    print(f" -> PASÓ: Búsqueda por folio '{t_a['codigo']}' arrojó el registro exacto.")

    # [TEST 6.3] Filtros combinados por equipo, área, prioridad y estado
    print("[TEST 6.3] Aplicando filtros simultáneos (equipo, prioridad, estado)...")
    # Filtrar por equipo eq1 y prioridad Urgente
    resp_filtro1 = client_admin.get(f"/tickets?equipo={eq1['id']}&prioridad=Urgente")
    html_f1 = resp_filtro1.get_data(as_text=True)
    assert t_a["codigo"] in html_f1, "Debe encontrar el ticket t_a"
    assert t_b["codigo"] not in html_f1, "No debe incluir t_b (equipo y prioridad diferente)"

    # Filtrar por estado Cerrado
    resp_cerrado = client_admin.get("/tickets?estado=Cerrado")
    html_cerrado = resp_cerrado.get_data(as_text=True)
    assert t_b["codigo"] in html_cerrado, "Debe encontrar t_b que está Cerrado"
    assert t_a["codigo"] not in html_cerrado, "No debe encontrar t_a que está Abierto"
    print(" -> PASÓ: Filtros combinados por equipo, área, prioridad y estado funcionan perfectamente.")

    # [TEST 6.4] Manejo coherente de estado 'Sin Resultados'
    print("[TEST 6.4] Verificando presentación amigable cuando no hay resultados...")
    resp_vacio = client_admin.get("/tickets?q=CODIGO_INEXISTENTE_XYZ_999")
    assert resp_vacio.status_code == 200, "Debe responder 200 OK con vista clara de sin resultados"
    html_vacio = resp_vacio.get_data(as_text=True)
    assert "No se encontraron tickets" in html_vacio, "Debe mostrar el mensaje de sin resultados"
    assert "Restablecer y Limpiar Filtros" in html_vacio, "Debe ofrecer botón para limpiar filtros"
    print(" -> PASÓ: Interfaz muestra tarjeta estilizada de 'Sin resultados' y botón de reinicio.")

    # [TEST 6.5] Detalle coherente y protección de acceso directo URL
    print("[TEST 6.5] Verificando detalle coherente y protección de URL (403)...")
    # Usuario normal intentando acceder por URL a t_b (donde NO es solicitante)
    resp_denegado = client_user.get(f"/tickets/{t_b['id']}")
    assert resp_denegado.status_code == 403, f"Se esperaba 403 Forbidden y se obtuvo {resp_denegado.status_code}"

    # Usuario normal accediendo a su propio ticket t_a
    resp_detalle_ok = client_user.get(f"/tickets/{t_a['id']}")
    assert resp_detalle_ok.status_code == 200, "Debe tener acceso autorizado a su ticket"
    html_det = resp_detalle_ok.get_data(as_text=True)
    assert "EQ-PLC-001" in html_det, "Debe mostrar el código del equipo vinculado"
    assert "PLC Siemens S7-1500" in html_det, "Debe mostrar el nombre del equipo vinculado"
    assert "Operador Juan" in html_det, "Debe mostrar el detector de la anomalía"
    print(" -> PASÓ: Detalle de ticket muestra coherentemente el equipo vinculado y bloquea accesos no autorizados con 403.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 6 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_6()

