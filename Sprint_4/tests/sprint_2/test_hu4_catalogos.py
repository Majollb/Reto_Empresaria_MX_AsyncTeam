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

def test_historia_usuario_4():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 4: CATÁLOGOS Y EQUIPOS")
    print("=" * 70)

    init_db(force_reset=True)
    client = app.test_client()

    # Iniciar sesión como Admin predeterminado (admin@sistema.mx / Admin123)
    login_resp = client.post("/login", data={
        "identificador": "admin@sistema.mx",
        "password": "Admin123"
    }, follow_redirects=True)
    assert login_resp.status_code == 200, "Error en login de administrador"

    # [TEST 4.1] Consultar equipos activos y datos iniciales demostrados
    print("[TEST 4.1] Consultando equipos activos y demostración de catálogo inicial...")
    activos = EquipmentModel.get_active()
    assert len(activos) >= 5, "Deben existir equipos activos precargados en el catálogo"
    for eq in activos:
        assert eq["estado"] == "Activo", f"El equipo {eq['codigo']} debería estar Activo"
        assert eq["area_nombre"], f"El equipo {eq['codigo']} debe tener un área asociada"
        assert eq["periodicidad_dias"] > 0, "Debe tener periodicidad configurada en días"
    print(f" -> PASÓ: {len(activos)} equipos activos disponibles con atributos completos.")

    # [TEST 4.2] Administrador mantiene catálogos (crear área y equipo)
    print("[TEST 4.2] Administrador registra nueva área y nuevo equipo industrial...")
    # Crear área
    area_resp = client.post("/admin/areas", data={
        "codigo": "AREA-TEST-99",
        "nombre": "Área de Pruebas Automatizadas",
        "descripcion": "Zona destinada a ensayos de fatiga y pruebas térmicas",
        "estado": "Activo"
    }, follow_redirects=True)
    assert area_resp.status_code == 200, "Error al crear área como admin"
    
    nueva_area = AreaModel.get_all()[0] # buscar área
    area_id = [a["id"] for a in AreaModel.get_all() if a["codigo"] == "AREA-TEST-99"][0]

    # Crear equipo
    eq_resp = client.post("/equipos/nuevo", data={
        "codigo": "EQ-ROB-099",
        "nombre": "Robot Colaborativo Universal UR10e",
        "marca": "Universal Robots",
        "modelo": "UR10e 6-Ejes",
        "numero_serie": "SN-UR-2026-9999",
        "area_id": str(area_id),
        "ubicacion_especifica": "Mesa de Ensamble 5",
        "periodicidad_dias": "45",
        "fecha_ultimo_mantenimiento": "2026-10-15",
        "estado": "Activo"
    }, follow_redirects=True)
    assert eq_resp.status_code == 200, "Error al crear equipo como admin"

    eq_creado = EquipmentModel.get_by_codigo("EQ-ROB-099")
    assert eq_creado is not None, "El nuevo equipo debe existir en la base de datos"
    assert eq_creado["periodicidad_dias"] == 45, "La periodicidad preventiva debe ser 45 días"
    print(" -> PASÓ: Administrador creó área y equipo con periodicidad configurada correctamente.")

    # [TEST 4.3] Usuario sin rol Admin no puede gestionar catálogos ni equipos (HTTP 403)
    print("[TEST 4.3] Verificando restricción RBAC: usuario no admin intentando dar de alta equipo...")
    # Crear usuario técnico
    UserModel.create_user("tecnico_cat", "tecnico_cat@sistema.mx", "Clave123", "Técnico Catálogo", "Responsable", "Activo")
    client_tech = app.test_client()
    client_tech.post("/login", data={"identificador": "tecnico_cat", "password": "Clave123"})
    
    resp_forbidden = client_tech.post("/equipos/nuevo", data={"codigo": "EQ-FAIL", "nombre": "Fail"}, follow_redirects=False)
    assert resp_forbidden.status_code == 403, f"Se esperaba 403 Forbidden y se obtuvo {resp_forbidden.status_code}"
    print(" -> PASÓ: Operación indebida de alta de equipo rechazada con HTTP 403 para rol Responsable.")

    # [TEST 4.4] Configuración y cálculo de periodicidad preventiva
    print("[TEST 4.4] Verificando cálculo de periodicidad y estado de mantenimiento preventivo...")
    info = EquipmentModel.calculate_maintenance_info("2026-10-01", 30)
    assert "proximo" in info, "Debe calcular la fecha del próximo mantenimiento"
    assert "status_texto" in info, "Debe indicar el estado del mantenimiento"
    print(f" -> PASÓ: Próximo mantenimiento calculado: {info['proximo']} ({info['status_texto']}).")

    # [TEST 4.5] Conservar referencias históricas al desactivar equipo
    print("[TEST 4.5] Verificando conservación de referencias históricas al desactivar un equipo...")
    # Crear un ticket vinculado al equipo EQ-ROB-099
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    ticket, err = TicketModel.create_ticket(
        titulo="Mantenimiento preventivo inicial UR10e",
        situacion_problema="Revisión de torque en tornillería de articulaciones y verificación de gripper neumático.",
        detector_nombre="Técnico de Turno",
        equipo_id=eq_creado["id"],
        categoria="Mantenimiento Preventivo",
        prioridad="Media",
        solicitante_id=admin_user["id"]
    )
    assert ticket is not None, f"Error al crear ticket: {err}"
    assert ticket["equipo_id"] == eq_creado["id"], "El ticket debe estar vinculado al equipo"

    # Desactivar el equipo
    desactivado, err = EquipmentModel.toggle_status(eq_creado["id"])
    assert err is None, f"Error al desactivar equipo: {err}"
    assert desactivado["estado"] == "Inactivo", "El equipo debe quedar en estado Inactivo"

    # Verificar que el ticket histórico SIGUE existiendo y conserva la referencia completa al equipo
    ticket_historico = TicketModel.get_by_id(ticket["id"])
    assert ticket_historico is not None, "El ticket histórico no debe ser eliminado"
    assert ticket_historico["equipo_codigo"] == "EQ-ROB-099", "La referencia histórica al código del equipo debe preservarse"
    assert ticket_historico["equipo_estado"] == "Inactivo", "Debe reflejar el estado actual del equipo sin romper relación"
    print(" -> PASÓ: Desactivar equipo conservó íntegramente la referencia histórica y trazabilidad en el ticket.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 4 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_4()


