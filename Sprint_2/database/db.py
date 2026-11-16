import sqlite3
import os
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from config import DATABASE_PATH, BASE_DIR, DATABASE_URL
from auth.security import hash_password

def get_db_connection():
    """
    Retorna una conexión a base de datos.
    Soporta PostgreSQL si DATABASE_URL está configurado, o SQLite por defecto.
    """
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            return conn
        except ImportError:
            pass  # Fallback a SQLite si psycopg2 no está instalado en el entorno local

    os.makedirs(DATABASE_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(force_reset=False):
    """
    Crea las tablas y precarga datos iniciales de HU-01 a HU-09 (Sprints 1, 2 y 3).
    El ÚNICO usuario predeterminado es admin@sistema.mx con acceso total.
    """
    conn = get_db_connection()
    schema_path = BASE_DIR / "database" / "schema.sql"

    if force_reset:
        conn.execute("DROP TABLE IF EXISTS ticket_adjuntos;")
        conn.execute("DROP TABLE IF EXISTS ticket_historial;")
        conn.execute("DROP TABLE IF EXISTS tickets;")
        conn.execute("DROP TABLE IF EXISTS equipos;")
        conn.execute("DROP TABLE IF EXISTS catalogos;")
        conn.execute("DROP TABLE IF EXISTS areas;")
        conn.execute("DROP TABLE IF EXISTS usuarios;")
        conn.commit()
    
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Migraciones no destructivas para bases SQLite ya inicializadas
    columnas_nuevas = [
        ("tickets", "ticket_relacionado_id", "INTEGER REFERENCES tickets(id)"),
        ("tickets", "motivo_reasignacion", "TEXT"),
        ("tickets", "motivo_espera", "TEXT"),
        ("tickets", "motivo_cancelacion", "TEXT"),
        ("tickets", "fecha_inicio_atencion", "TIMESTAMP"),
        ("tickets", "fecha_resolucion", "TIMESTAMP"),
        ("tickets", "fecha_cierre", "TIMESTAMP"),
        ("tickets", "tiempo_espera_minutos", "INTEGER DEFAULT 0"),
        ("tickets", "ultima_fecha_espera", "TIMESTAMP"),
        ("ticket_adjuntos", "usuario_id", "INTEGER REFERENCES usuarios(id)"),
        ("ticket_historial", "responsable_anterior_id", "INTEGER REFERENCES usuarios(id)"),
        ("ticket_historial", "responsable_nuevo_id", "INTEGER REFERENCES usuarios(id)"),
        ("ticket_historial", "motivo_detalle", "TEXT")
    ]
    for tabla, col, tipo in columnas_nuevas:
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo};")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios;")
    user_count = cursor.fetchone()[0]
    
    if user_count == 0:
        print("[BD] Inicializando usuario administrador por defecto (admin@sistema.mx)...")
        
        # Único usuario predeterminado: admin@sistema.mx / Admin123
        users_seed = [
            ("admin", "admin@sistema.mx", "Admin123", "Administrador del Sistema", "Admin", "Activo")
        ]
        
        for username, email, pwd, nombre, rol, estado in users_seed:
            pwd_hash, salt = hash_password(pwd)
            cursor.execute("""
                INSERT INTO usuarios (username, email, password_hash, salt, nombre_completo, rol, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (username, email, pwd_hash, salt, nombre, rol, estado))
            
        conn.commit()
        
        # Recuperar ID del admin
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin';")
        admin_id = cursor.fetchone()["id"]

        # =====================================================================
        # SPRINT 2: CATÁLOGOS BÁSICOS - ÁREAS INDUSTRIALES (HU-04)
        # =====================================================================
        print("[BD] Precargando catálogo de áreas industriales (HU-04)...")
        areas_seed = [
            ("AREA-PROD-01", "Línea de Ensamble y Producción", "Línea principal de manufactura automatizada y bandas transportadoras", "Activo"),
            ("AREA-ROB-02", "Celda de Soldadura Robótica", "Celda automatizada con robots industriales Fanuc y estaciones de soldadura", "Activo"),
            ("AREA-MEC-03", "Taller de Maquinado y Control CNC", "Área de maquinado de alta precisión y tornos CNC", "Activo"),
            ("AREA-ELEC-04", "Subestación y Cuarto de Control", "Transformadores, tableros de potencia y distribución eléctrica", "Activo"),
            ("AREA-SERV-05", "Servicios de Aire y Enfriamiento", "Compresores industriales de tornillo y chillers de enfriamiento", "Activo"),
            ("AREA-ALM-06", "Almacén de Refacciones y Materia Prima", "Almacén general y control de inventario", "Inactivo")
        ]
        for codigo, nombre, desc, estado in areas_seed:
            cursor.execute("""
                INSERT INTO areas (codigo, nombre, descripcion, estado)
                VALUES (?, ?, ?, ?);
            """, (codigo, nombre, desc, estado))
        conn.commit()

        # =====================================================================
        # SPRINT 2: CATÁLOGOS AUXILIARES (Categorías, Prioridades)
        # =====================================================================
        catalogos_seed = [
            ("categoria_ticket", "AUTO", "Automatización Industrial", "PLCs, Variadores, Servomotores, HMIs y Sensores", "Activo"),
            ("categoria_ticket", "PREV", "Mantenimiento Preventivo", "Rutinas programadas de lubricación, limpieza e inspección", "Activo"),
            ("categoria_ticket", "CORR", "Mantenimiento Correctivo", "Reparación de averías inesperadas y paros no programados", "Activo"),
            ("categoria_ticket", "ELEC", "Electricidad y Fuerza", "Tableros eléctricos, arrancadores, cableado y subestaciones", "Activo"),
            ("categoria_ticket", "MEC", "Mecánica y Neumática", "Compresores, actuadores neumáticos, bandas y rodamientos", "Activo"),
            ("categoria_ticket", "RED", "Redes y Comunicaciones", "Switches industriales, Profinet, Ethernet/IP y SCADA", "Activo")
        ]
        for tipo, clave, valor, desc, est in catalogos_seed:
            cursor.execute("""
                INSERT INTO catalogos (tipo, clave, valor, descripcion, estado)
                VALUES (?, ?, ?, ?, ?);
            """, (tipo, clave, valor, desc, est))
        conn.commit()

        # =====================================================================
        # SPRINT 2: CATÁLOGO DE EQUIPOS Y ACTIVOS INDUSTRIALES (HU-04)
        # =====================================================================
        print("[BD] Precargando inventario de equipos con periodicidad preventiva (HU-04)...")
        cursor.execute("SELECT id, codigo FROM areas;")
        area_map = {row["codigo"]: row["id"] for row in cursor.fetchall()}

        equipos_seed = [
            (
                "EQ-PLC-001",
                "PLC Siemens S7-1500 Línea 1",
                "Siemens",
                "Simatic CPU 1516-3 PN/DP",
                "SN-SIE-2024-001",
                area_map["AREA-PROD-01"],
                "Gabinete Principal de Control G-01",
                60,
                "2026-09-15",
                "Activo"
            ),
            (
                "EQ-ROB-002",
                "Robot Industrial Fanuc M-20iD",
                "Fanuc",
                "M-20iD/25 con Controlador R-30iB",
                "SN-FAN-2023-458",
                area_map["AREA-ROB-02"],
                "Celda de Soldadura E-02",
                90,
                "2026-08-10",
                "Activo"
            ),
            (
                "EQ-CNC-003",
                "Centro de Maquinado CNC Haas VF-2",
                "Haas Automation",
                "VF-2 Super Speed 4-Ejes",
                "SN-HAA-2022-789",
                area_map["AREA-MEC-03"],
                "Bahía Mecánica 3",
                180,
                "2026-05-20",
                "Activo"
            ),
            (
                "EQ-CMP-004",
                "Compresor de Tornillo Atlas Copco GA37",
                "Atlas Copco",
                "GA 37 VSD+ Workplace",
                "SN-ATC-2024-112",
                area_map["AREA-SERV-05"],
                "Cuarto de Compresores Principal",
                30,
                "2026-10-01",
                "Activo"
            ),
            (
                "EQ-VAR-005",
                "Variador de Frecuencia Danfoss VLT 55kW",
                "Danfoss",
                "VLT AutomationDrive FC-302",
                "SN-DAN-2023-903",
                area_map["AREA-PROD-01"],
                "Tablero de Variadores T-VAR-02",
                90,
                "2026-07-12",
                "Activo"
            ),
            (
                "EQ-TRA-006",
                "Transformador Principal 500 kVA",
                "Prolec GE",
                "T-500K Tipo Seco 23kV/480V",
                "SN-PRO-2021-331",
                area_map["AREA-ELEC-04"],
                "Subestación Eléctrica General",
                365,
                "2025-11-15",
                "Activo"
            ),
            (
                "EQ-OBS-007",
                "Banda Transportadora Desactivada (Histórico)",
                "Interroll",
                "RollerDrive RM-8320",
                "SN-INT-2018-099",
                area_map["AREA-PROD-01"],
                "Línea de Salida Antigua",
                120,
                "2024-02-10",
                "Inactivo"
            )
        ]

        for cod, nom, marca, mod, serie, a_id, ubic, per, ult_m, est in equipos_seed:
            cursor.execute("""
                INSERT INTO equipos (codigo, nombre, marca, modelo, numero_serie, area_id, ubicacion_especifica, periodicidad_dias, fecha_ultimo_mantenimiento, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (cod, nom, marca, mod, serie, a_id, ubic, per, ult_m, est))
        conn.commit()

        cursor.execute("SELECT id, codigo FROM equipos;")
        eq_map = {row["codigo"]: row["id"] for row in cursor.fetchall()}

        # =====================================================================
        # SPRINT 2 Y 3: SEMBRAR TICKETS CON HISTORIAL Y TIEMPOS
        # =====================================================================
        print("[BD] Precargando tickets relacionados con equipos (HU-05 a HU-09)...")
        tickets_seed = [
            (
                "TK-2026-001",
                "Fallo en variador de frecuencia PLC Línea 3",
                "El variador de frecuencia de la banda transportadora principal presenta código de error E-04 (Sobrecarga de motor). Se requiere diagnóstico técnico urgente.",
                "Fallo intermitente con disparo térmico al alcanzar 80% de carga.",
                "Ing. Roberto Salazar (Líder Turno Matutino)",
                "Automatización Industrial",
                "Urgente",
                "En Proceso",
                admin_id,
                admin_id,
                eq_map["EQ-VAR-005"],
                area_map["AREA-PROD-01"],
                "Nave Industrial B - Tablero T-VAR-02"
            ),
            (
                "TK-2026-002",
                "Mantenimiento preventivo programado compresor",
                "Revisión de niveles de aceite sintético, reemplazo de cartucho de filtro separador y chequeo de purga automática.",
                "Rutina preventiva mensual según especificación técnica del fabricante.",
                "Téc. Mantenimiento Preventivo",
                "Mantenimiento Preventivo",
                "Media",
                "Abierto",
                admin_id,
                None,  # Sin asignar para demostrar HU-07
                eq_map["EQ-CMP-004"],
                area_map["AREA-SERV-05"],
                "Cuarto de Compresores Principal"
            ),
            (
                "TK-2026-003",
                "Calibración de servomotor y juego en eje 4 robot Fanuc",
                "El brazo robótico reporta desviación milimétrica en la estación de soldadura de chasis.",
                "Se detectó vibración anormal al realizar el movimiento de posicionamiento fino en el eje J4.",
                "Operador de Celda Cel-02",
                "Mantenimiento Correctivo",
                "Alta",
                "En Espera",
                admin_id,
                admin_id,
                eq_map["EQ-ROB-002"],
                area_map["AREA-ROB-02"],
                "Celda de Soldadura E-02"
            ),
            (
                "TK-2026-004",
                "Registro histórico en equipo desactivado",
                "Ticket previo completado antes de dar de baja la banda transportadora antigua.",
                "Reemplazo preventivo de baleros y rodillos motrices.",
                "Supervisor de Mantenimiento",
                "Mantenimiento Preventivo",
                "Baja",
                "Cerrado",
                admin_id,
                admin_id,
                eq_map["EQ-OBS-007"],
                area_map["AREA-PROD-01"],
                "Línea de Salida Antigua"
            )
        ]
        
        for codigo, titulo, desc, sit, detector, cat, prio, est, sol_id, resp_id, eq_id, a_id, ubic in tickets_seed:
            cursor.execute("""
                INSERT INTO tickets (codigo, titulo, descripcion, situacion_problema, detector_nombre, categoria, prioridad, estado, solicitante_id, responsable_id, equipo_id, area_id, ubicacion_equipo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (codigo, titulo, desc, sit, detector, cat, prio, est, sol_id, resp_id, eq_id, a_id, ubic))
            
            t_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO ticket_historial (ticket_id, usuario_id, accion, comentario, estado_nuevo)
                VALUES (?, ?, 'Registro Inicial', 'Ticket registrado en el sistema con equipo vinculado.', ?);
            """, (t_id, admin_id, est))

        conn.commit()
        
    conn.close()
    print("[BD] Base de datos inicializada con éxito.")

if __name__ == "__main__":
    init_db(force_reset=True)
