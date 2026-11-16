import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

site_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for p in site_candidates:
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app import app
from database.db import init_db
from models.ticket import TicketModel

def test_historia_usuario_2():
    print("\n" + "="*70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 2 (FLASK): ROLES Y PARTICIPACIÓN")
    print("="*70)

    init_db(force_reset=True)
    app.config["TESTING"] = True

    # Registrar usuarios para pruebas de RBAC
    from models.user import UserModel
    from database.db import get_db_connection
    u_user, _ = UserModel.create_user("usrtest", "usuario@sistema.mx", "User123", "Usuario Solicitante Test", "Usuario", "Activo")
    u_resp, _ = UserModel.create_user("resptest", "tecnico@sistema.mx", "Tecnico123", "Técnico Responsable Test", "Responsable", "Activo")

    conn = get_db_connection()
    conn.execute("UPDATE tickets SET solicitante_id = ?, responsable_id = ? WHERE codigo = 'TK-2026-001';", (u_user["id"], u_resp["id"]))
    conn.execute("UPDATE tickets SET solicitante_id = ?, responsable_id = ? WHERE codigo = 'TK-2026-002';", (u_user["id"], u_resp["id"]))
    conn.commit()
    conn.close()

    # Clientes de prueba para cada rol
    client_user = app.test_client()
    client_resp = app.test_client()
    client_admin = app.test_client()

    client_user.post("/login", data={"identificador": "usuario@sistema.mx", "password": "User123"})
    client_resp.post("/login", data={"identificador": "tecnico@sistema.mx", "password": "Tecnico123"})
    client_admin.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})

    print("[INFO] Sesiones iniciadas exitosamente en Flask para Admin, Responsable y Usuario.")

    # -------------------------------------------------------------
    # PRUEBAS PARA ROL: USUARIO (SOLICITANTE)
    # -------------------------------------------------------------
    print("\n[TEST 2.1] Usuario consulta listado de tickets (/tickets)...")
    res_t_user = client_user.get("/tickets")
    assert res_t_user.status_code == 200
    html_u = res_t_user.data.decode("utf-8")
    assert "TK-2026-001" in html_u
    assert "TK-2026-002" in html_u
    assert "TK-2026-003" not in html_u
    print(" -> PASÓ: Usuario solo visualiza tickets donde es solicitante.")

    print("[TEST 2.2] Usuario intenta acceso directo URL a ticket ajeno (/tickets/3)...")
    res_direct_blocked = client_user.get("/tickets/3")
    assert res_direct_blocked.status_code == 403, f"Esperado 403, obtenido {res_direct_blocked.status_code}"
    assert "403" in res_direct_blocked.data.decode("utf-8") or "Acceso Denegado" in res_direct_blocked.data.decode("utf-8")
    print(" -> PASÓ: Acceso directo restringido por el servidor retornando HTTP 403 Forbidden.")

    print("[TEST 2.3] Usuario intenta operación indebida (modificar estado de ticket ajeno)...")
    ticket_3_before = TicketModel.get_by_id(3)
    status_before = ticket_3_before["estado"]
    res_mod_blocked = client_user.post("/tickets/3/status", data={"estado": "Cerrado"})
    assert res_mod_blocked.status_code == 403
    ticket_3_after = TicketModel.get_by_id(3)
    assert ticket_3_after["estado"] == status_before, "El estado del ticket no debió cambiar"
    print(" -> PASÓ: Operación indebida rechazada con 403 sin modificar los datos en BD.")

    print("[TEST 2.4] Usuario intenta ingresar directamente al panel de administración (/admin/usuarios)...")
    res_admin_blocked = client_user.get("/admin/usuarios")
    assert res_admin_blocked.status_code == 403
    print(" -> PASÓ: Panel de administración bloqueado para rol Usuario.")

    # -------------------------------------------------------------
    # PRUEBAS PARA ROL: RESPONSABLE TÉCNICO
    # -------------------------------------------------------------
    print("\n[TEST 2.5] Responsable técnico consulta listado (/tickets)...")
    res_t_resp = client_resp.get("/tickets")
    html_r = res_t_resp.data.decode("utf-8")
    assert "TK-2026-001" in html_r
    assert "TK-2026-003" not in html_r
    print(" -> PASÓ: Responsable solo visualiza tickets donde tiene asignación técnica.")

    print("[TEST 2.6] Responsable intenta consultar ticket donde NO participa (/tickets/3)...")
    res_resp_blocked = client_resp.get("/tickets/3")
    assert res_resp_blocked.status_code == 403
    print(" -> PASÓ: Acceso denegado con 403 al responsable para tickets fuera de su asignación.")

    print("[TEST 2.7] Responsable actualiza estado de SU ticket asignado (/tickets/1/status)...")
    res_status_ok = client_resp.post("/tickets/1/status", data={"estado": "En Espera", "comentario": "En espera de refacción"}, follow_redirects=False)
    assert res_status_ok.status_code == 302
    ticket_1 = TicketModel.get_by_id(1)
    assert ticket_1["estado"] == "En Espera"
    print(" -> PASÓ: Usuario autorizado ejecuta correctamente su acción de actualización de estado.")

    print("[TEST 2.8] Responsable intenta reasignar responsable (acción exclusiva de Admin)...")
    res_reassign_blocked = client_resp.post("/tickets/1/reassign", data={"responsable_id": "1"})
    assert res_reassign_blocked.status_code == 403
    print(" -> PASÓ: Reasignación rechazada para técnico (exclusivo para Administrador).")

    # -------------------------------------------------------------
    # PRUEBAS PARA ROL: ADMINISTRADOR
    # -------------------------------------------------------------
    print("\n[TEST 2.9] Administrador consulta tickets y accede a gestión...")
    res_t_admin = client_admin.get("/tickets")
    html_a = res_t_admin.data.decode("utf-8")
    assert "TK-2026-001" in html_a
    assert "TK-2026-002" in html_a
    assert "TK-2026-003" in html_a
    print(" -> PASÓ: Administrador visualiza la totalidad de los tickets.")

    print("[TEST 2.10] Administrador reasigna responsable en ticket 3...")
    res_reassign_ok = client_admin.post("/tickets/3/reassign", data={"responsable_id": str(u_resp["id"]), "motivo": "Asignado a técnico certificado"}, follow_redirects=False)
    assert res_reassign_ok.status_code == 302
    t3 = TicketModel.get_by_id(3)
    assert t3["responsable_id"] == u_resp["id"]
    print(" -> PASÓ: Administrador ejecuta reasignación de responsable con éxito.")

    print("[TEST 2.11] Administrador accede a módulo de gestión de usuarios...")
    res_users_ok = client_admin.get("/admin/usuarios")
    assert res_users_ok.status_code == 200
    assert "Administración y Mantenimiento de Cuentas" in res_users_ok.data.decode("utf-8")
    print(" -> PASÓ: Acceso autorizado al panel de usuarios concedido a Administrador.")

    print("="*70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 2 (FLASK) VERIFICADOS EXITOSAMENTE!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_2()

