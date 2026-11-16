import os
import sys
import csv
import io
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
from models.sprint_4.reports import ReportsModel


def test_historia_usuario_12():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 12: RESUMEN, INDICADORES Y CSV")
    print("=" * 70)

    init_db(force_reset=True)

    # 1. Crear usuarios y entorno de datos
    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    ti_manager, _ = UserModel.create_user("encargado_ti", "ti@sistema.mx", "Clave123", "Ing. Laura Méndez", "Responsable", "Activo")
    usuario_comun, _ = UserModel.create_user("empleado_gral", "empleado@sistema.mx", "Clave123", "Juan Pérez", "Usuario", "Activo")

    eq_plc = EquipmentModel.get_by_codigo("EQ-PLC-001")
    eq_rob = EquipmentModel.get_by_codigo("EQ-ROB-002")

    # 2. Generar tickets en diversas situaciones operativas
    # Ticket A: Resuelto con solución
    t_a, _ = TicketModel.create_ticket(
        titulo="Falla en módulo Profinet PLC",
        situacion_problema="Pérdida de enlace con rack remoto.",
        detector_nombre="Operador",
        equipo_id=eq_plc["id"],
        categoria="Automatización Industrial",
        prioridad="Alta",
        solicitante_id=usuario_comun["id"],
        responsable_id=ti_manager["id"]
    )
    TicketModel.update_status(t_a["id"], "En Proceso", ti_manager, "Inicio de diagnóstico")
    TicketModel.resolve_ticket(t_a["id"], ti_manager, "Se reconectó fibra óptica y se restauró comunicación.")
    TicketModel.close_ticket(t_a["id"], admin_user, "Con Solución", "Cierre satisfactorio.")

    # Ticket B: Cerrado sin solución justificada
    t_b, _ = TicketModel.create_ticket(
        titulo="Ruido en servomotor CNC descontinuado",
        situacion_problema="Desgaste en baleros de motor con 25 años de servicio.",
        detector_nombre="Mantenimiento",
        equipo_id=eq_rob["id"],
        categoria="Mantenimiento Correctivo",
        prioridad="Media",
        solicitante_id=admin_user["id"],
        responsable_id=ti_manager["id"]
    )
    TicketModel.close_ticket(t_b["id"], admin_user, "Sin Solución", "Modelo descontinuado sin refacciones disponibles; se solicita reemplazo.")

    # Ticket C: Recurrencia creada a partir del Ticket A
    t_c, _ = TicketModel.create_recurrence(
        ticket_id=t_a["id"],
        user=admin_user,
        situacion_falla="El módulo Profinet vuelve a parpadear en rojo tras reinicio de planta.",
        prioridad="Urgente"
    )

    # Ticket D: En Espera de refacciones
    t_d, _ = TicketModel.create_ticket(
        titulo="Falta de contactor principal",
        situacion_problema="Bobina de 24V quemada.",
        detector_nombre="Técnico",
        equipo_id=eq_plc["id"],
        categoria="Mantenimiento Eléctrico",
        prioridad="Alta",
        solicitante_id=admin_user["id"],
        responsable_id=ti_manager["id"]
    )
    TicketModel.update_status(t_d["id"], "En Proceso", ti_manager, "Evaluando contactor")
    TicketModel.update_status(t_d["id"], "En Espera", ti_manager, "Esperando llegada de refacción desde bodega central")

    # [TEST 12.1] Visualización de resumen y conteos según filtros
    print("[TEST 12.1] Verificando cálculo de métricas y conteos según filtros...")
    reporte_global = ReportsModel.get_summary(admin_user)
    assert reporte_global["total_tickets"] >= 4, f"Se esperaban al menos 4 tickets, se encontraron {reporte_global['total_tickets']}"
    assert "conteo_estados" in reporte_global
    assert "conteo_prioridades" in reporte_global
    assert "conteo_categorias" in reporte_global
    assert "tiempos_promedio" in reporte_global

    # Filtro por estado 'Cerrado'
    reporte_cerrados = ReportsModel.get_summary(admin_user, {"estado": "Cerrado"})
    assert reporte_cerrados["total_tickets"] >= 2, "Debe contabilizar tickets cerrados"
    assert all(t["estado"] == "Cerrado" for t in reporte_cerrados["tickets"]), "Todos los tickets en la lista deben ser Cerrados"
    print(" -> PASÓ: Conteo general y filtros por estado calculados con exactitud.")

    # [TEST 12.2] Distinción de situaciones operativas (solución, sin solución, recurrencias, esperas)
    print("[TEST 12.2] Verificando distinción analítica de situaciones operativas...")
    sit = reporte_global["situaciones"]
    assert sit["cerrados_con_solucion"] >= 1, "Debe contabilizar al menos 1 ticket cerrado con solución"
    assert sit["cerrados_sin_solucion"] >= 1, "Debe contabilizar al menos 1 ticket cerrado sin solución justificado"
    assert sit["recurrencias"] >= 1, "Debe contabilizar al menos 1 ticket de recurrencia"
    assert sit["en_espera"] >= 1, "Debe contabilizar tickets que están o estuvieron en espera"
    print(f" -> PASÓ: Situaciones distinguidas con precisión: {sit['cerrados_con_solucion']} con solución, {sit['cerrados_sin_solucion']} sin solución, {sit['recurrencias']} recurrencias, {sit['en_espera']} en espera.")

    # [TEST 12.3] Semáforo de mantenimientos preventivos (al día, próximo <= 7 días, vencido)
    print("[TEST 12.3] Verificando semáforo de mantenimientos preventivos de equipos...")
    prev_status = ReportsModel.get_preventive_maintenance_status()
    assert "totales" in prev_status
    assert "equipos" in prev_status
    totales = prev_status["totales"]
    assert "al_dia" in totales and "proximo" in totales and "vencido" in totales
    assert totales["total_equipos"] >= 6, "Debe evaluar los equipos del catálogo"
    print(f" -> PASÓ: Semáforo preventivo evaluado correctamente (Al Día: {totales['al_dia']}, Próximos: {totales['proximo']}, Vencidos: {totales['vencido']}).")

    # [TEST 12.4] Control de permisos por rol en el módulo de reportes (HTTP 403 vs 200)
    print("[TEST 12.4] Verificando control de acceso RBAC a reportes ejecutivos...")

    # Usuario solicitante no debe tener acceso a reportes (HTTP 403)
    client_user = app.test_client()
    client_user.post("/login", data={"identificador": "empleado_gral", "password": "Clave123"})
    resp_user_rep = client_user.get("/reportes")
    assert resp_user_rep.status_code == 403, f"Usuario común debe recibir 403 en /reportes y se obtuvo {resp_user_rep.status_code}"

    # Encargado de TI / Responsable sí tiene acceso (HTTP 200)
    client_ti = app.test_client()
    client_ti.post("/login", data={"identificador": "encargado_ti", "password": "Clave123"})
    resp_ti_rep = client_ti.get("/reportes")
    assert resp_ti_rep.status_code == 200, f"Encargado de TI debe tener acceso 200 en /reportes y se obtuvo {resp_ti_rep.status_code}"

    # Administrador sí tiene acceso (HTTP 200)
    client_admin = app.test_client()
    client_admin.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})
    resp_admin_rep = client_admin.get("/reportes")
    assert resp_admin_rep.status_code == 200, "Administrador debe tener acceso 200 en /reportes"
    print(" -> PASÓ: RBAC riguroso: 403 para usuarios generales, 200 para Encargados de TI y Administradores.")

    # [TEST 12.5] Exportación autorizada en formato CSV (RFC 4180 con BOM UTF-8)
    print("[TEST 12.5] Verificando exportación a archivo CSV verificable y compatible con Excel...")

    # Descarga HTTP de CSV
    resp_csv = client_admin.get("/reportes/exportar-csv")
    assert resp_csv.status_code == 200, f"Error en descarga CSV: {resp_csv.status_code}"
    assert "text/csv" in resp_csv.headers.get("Content-Type", "")
    assert "attachment; filename=" in resp_csv.headers.get("Content-Disposition", "")

    csv_raw = resp_csv.get_data(as_text=False)
    # Verificar presencia de BOM UTF-8 (\xef\xbb\xbf) para apertura directa en Microsoft Excel
    assert csv_raw.startswith(b"\xef\xbb\xbf"), "El archivo CSV debe iniciar con BOM UTF-8 para garantizar caracteres en Excel"

    # Decodificar y parsear con módulo estándar csv
    csv_text = csv_raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) >= 5, "El CSV debe contener la fila de encabezados más las filas de datos de tickets"

    headers = rows[0]
    expected_headers = [
        "Folio", "Título", "Situación Problema", "Categoría", "Prioridad",
        "Estado Actual", "Tipo de Cierre", "Solución / Justificación Técnica",
        "Motivo Sin Solución", "Es Recurrencia", "Equipo Código", "Equipo Nombre",
        "Solicitante (Creador)", "Responsable Técnico", "Fecha de Registro",
        "Fecha de Resolución", "Fecha de Cierre"
    ]
    for h in expected_headers:
        assert h in headers, f"Encabezado requerido '{h}' no encontrado en el archivo CSV generado"

    # Verificar que el ticket de recurrencia aparezca con 'Sí' en columna Es Recurrencia
    idx_rec = headers.index("Es Recurrencia")
    idx_folio = headers.index("Folio")
    recurrence_rows = [r for r in rows[1:] if r[idx_rec] == "Sí"]
    assert len(recurrence_rows) >= 1, "El CSV debe distinguir claramente los tickets que son recurrencias ('Sí')"

    print(f" -> PASÓ: Archivo CSV generado exitosamente ({len(rows)-1} registros), con BOM UTF-8 y encabezados completos.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 12 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70)


if __name__ == "__main__":
    test_historia_usuario_12()
