import datetime
from database.db import get_db_connection

class AreaModel:
    @staticmethod
    def get_all(active_only: bool = False):
        conn = get_db_connection()
        query = "SELECT * FROM areas"
        params = []
        if active_only:
            query += " WHERE estado = 'Activo'"
        query += " ORDER BY nombre ASC;"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(area_id: int):
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM areas WHERE id = ?;", (area_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create_area(codigo: str, nombre: str, descripcion: str = "", estado: str = "Activo"):
        if not codigo or not codigo.strip():
            return None, "El código del área es obligatorio."
        if not nombre or not nombre.strip():
            return None, "El nombre del área es obligatorio."

        clean_codigo = codigo.strip().upper()
        clean_nombre = nombre.strip()

        conn = get_db_connection()
        # Verificar unicidad
        existing = conn.execute("SELECT id FROM areas WHERE lower(codigo) = lower(?) OR lower(nombre) = lower(?);", (clean_codigo, clean_nombre)).fetchone()
        if existing:
            conn.close()
            return None, "Ya existe un área con el mismo código o nombre."

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO areas (codigo, nombre, descripcion, estado)
            VALUES (?, ?, ?, ?);
        """, (clean_codigo, clean_nombre, (descripcion or "").strip(), estado))
        conn.commit()
        area_id = cursor.lastrowid
        conn.close()
        return AreaModel.get_by_id(area_id), None

    @staticmethod
    def update_area(area_id: int, codigo: str, nombre: str, descripcion: str, estado: str):
        if not codigo or not codigo.strip():
            return None, "El código del área es obligatorio."
        if not nombre or not nombre.strip():
            return None, "El nombre del área es obligatorio."

        clean_codigo = codigo.strip().upper()
        clean_nombre = nombre.strip()

        conn = get_db_connection()
        existing = conn.execute(
            "SELECT id FROM areas WHERE (lower(codigo) = lower(?) OR lower(nombre) = lower(?)) AND id != ?;",
            (clean_codigo, clean_nombre, area_id)
        ).fetchone()
        if existing:
            conn.close()
            return None, "Ya existe otra área con el mismo código o nombre."

        conn.execute("""
            UPDATE areas
            SET codigo = ?, nombre = ?, descripcion = ?, estado = ?
            WHERE id = ?;
        """, (clean_codigo, clean_nombre, (descripcion or "").strip(), estado, area_id))
        conn.commit()
        conn.close()
        return AreaModel.get_by_id(area_id), None

    @staticmethod
    def toggle_status(area_id: int):
        conn = get_db_connection()
        row = conn.execute("SELECT estado FROM areas WHERE id = ?;", (area_id,)).fetchone()
        if not row:
            conn.close()
            return None, "Área no encontrada."
        nuevo_estado = "Inactivo" if row["estado"] == "Activo" else "Activo"
        conn.execute("UPDATE areas SET estado = ? WHERE id = ?;", (nuevo_estado, area_id))
        conn.commit()
        conn.close()
        return AreaModel.get_by_id(area_id), None


class EquipmentModel:
    @staticmethod
    def calculate_maintenance_info(fecha_ultimo_str: str, periodicidad_dias: int) -> dict:
        """Calcula el estado del mantenimiento preventivo (HU-04)."""
        if not fecha_ultimo_str or not periodicidad_dias:
            return {
                "proximo": "No programado",
                "dias_restantes": None,
                "status_badge": "badge-neutral",
                "status_texto": "Sin programar"
            }
        try:
            ultimo = datetime.datetime.strptime(str(fecha_ultimo_str)[:10], "%Y-%m-%d").date()
            proximo = ultimo + datetime.timedelta(days=int(periodicidad_dias))
            hoy = datetime.date.today()
            delta = (proximo - hoy).days

            if delta < 0:
                return {
                    "proximo": proximo.strftime("%Y-%m-%d"),
                    "dias_restantes": delta,
                    "status_badge": "badge-danger",
                    "status_texto": f"Vencido ({abs(delta)} días)"
                }
            elif delta <= 7:
                return {
                    "proximo": proximo.strftime("%Y-%m-%d"),
                    "dias_restantes": delta,
                    "status_badge": "badge-warning",
                    "status_texto": f"Próximo ({delta} días)"
                }
            else:
                return {
                    "proximo": proximo.strftime("%Y-%m-%d"),
                    "dias_restantes": delta,
                    "status_badge": "badge-success",
                    "status_texto": f"Al día ({delta} días)"
                }
        except Exception:
            return {
                "proximo": "Fecha inválida",
                "dias_restantes": None,
                "status_badge": "badge-neutral",
                "status_texto": "Desconocido"
            }

    @staticmethod
    def get_by_id(equipment_id: int):
        conn = get_db_connection()
        query = """
            SELECT e.*, a.nombre AS area_nombre, a.codigo AS area_codigo
            FROM equipos e
            JOIN areas a ON e.area_id = a.id
            WHERE e.id = ?;
        """
        row = conn.execute(query, (equipment_id,)).fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["mantenimiento_info"] = EquipmentModel.calculate_maintenance_info(
            res.get("fecha_ultimo_mantenimiento"), res.get("periodicidad_dias")
        )
        return res

    @staticmethod
    def get_by_codigo(codigo: str):
        if not codigo:
            return None
        conn = get_db_connection()
        query = """
            SELECT e.*, a.nombre AS area_nombre, a.codigo AS area_codigo
            FROM equipos e
            JOIN areas a ON e.area_id = a.id
            WHERE lower(e.codigo) = lower(?);
        """
        row = conn.execute(query, (codigo.strip(),)).fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["mantenimiento_info"] = EquipmentModel.calculate_maintenance_info(
            res.get("fecha_ultimo_mantenimiento"), res.get("periodicidad_dias")
        )
        return res

    @staticmethod
    def get_active():
        """Retorna únicamente los equipos activos para selección en solicitudes de tickets (HU-05)."""
        return EquipmentModel.get_all(active_only=True)

    @staticmethod
    def get_all(active_only: bool = False, search: str = None, area_id: int = None, estado: str = None):
        """Lista equipos con filtros opcionales de búsqueda, área y estado (HU-04)."""
        conn = get_db_connection()
        query = """
            SELECT e.*, a.nombre AS area_nombre, a.codigo AS area_codigo,
                   (SELECT COUNT(*) FROM tickets t WHERE t.equipo_id = e.id) AS total_tickets
            FROM equipos e
            JOIN areas a ON e.area_id = a.id
            WHERE 1=1
        """
        params = []
        if active_only:
            query += " AND e.estado = 'Activo'"

        if search:
            query += " AND (e.codigo LIKE ? OR e.nombre LIKE ? OR e.marca LIKE ? OR e.modelo LIKE ? OR e.numero_serie LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term, term, term])

        if area_id:
            query += " AND e.area_id = ?"
            params.append(area_id)

        if estado and estado in ('Activo', 'Inactivo', 'En Mantenimiento', 'Fuera de Servicio'):
            query += " AND e.estado = ?"
            params.append(estado)

        query += " ORDER BY e.estado ASC, e.codigo ASC;"
        rows = conn.execute(query, params).fetchall()
        conn.close()

        result = []
        for r in rows:
            d = dict(r)
            d["mantenimiento_info"] = EquipmentModel.calculate_maintenance_info(
                d.get("fecha_ultimo_mantenimiento"), d.get("periodicidad_dias")
            )
            result.append(d)
        return result

    @staticmethod
    def create_equipment(
        codigo: str,
        nombre: str,
        marca: str,
        modelo: str,
        numero_serie: str,
        area_id: int,
        ubicacion_especifica: str = "",
        periodicidad_dias: int = 90,
        fecha_ultimo_mantenimiento: str = None,
        estado: str = "Activo"
    ):
        """Registra un nuevo equipo validando atributos obligatorios y unicidad (HU-04)."""
        if not codigo or not codigo.strip():
            return None, "El código del equipo es obligatorio."
        if not nombre or not nombre.strip():
            return None, "El nombre del equipo es obligatorio."
        if not marca or not marca.strip():
            return None, "La marca del equipo es obligatoria."
        if not modelo or not modelo.strip():
            return None, "El modelo del equipo es obligatorio."
        if not numero_serie or not numero_serie.strip():
            return None, "El número de serie es obligatorio."
        if not area_id:
            return None, "Debe seleccionar un área de localización."

        try:
            periodicidad = int(periodicidad_dias)
            if periodicidad <= 0:
                return None, "La periodicidad preventiva debe ser mayor a 0 días."
        except (ValueError, TypeError):
            return None, "La periodicidad preventiva debe ser un número entero en días."

        clean_codigo = codigo.strip().upper()
        clean_serie = numero_serie.strip()

        conn = get_db_connection()
        # Verificar unicidad de código y número de serie
        existing = conn.execute("""
            SELECT id FROM equipos 
            WHERE lower(codigo) = lower(?) OR lower(numero_serie) = lower(?);
        """, (clean_codigo, clean_serie)).fetchone()

        if existing:
            conn.close()
            return None, "Ya existe un equipo con ese código o número de serie."

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO equipos (
                codigo, nombre, marca, modelo, numero_serie, area_id, 
                ubicacion_especifica, periodicidad_dias, fecha_ultimo_mantenimiento, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            clean_codigo,
            nombre.strip(),
            marca.strip(),
            modelo.strip(),
            clean_serie,
            area_id,
            (ubicacion_especifica or "").strip(),
            periodicidad,
            fecha_ultimo_mantenimiento or None,
            estado
        ))
        conn.commit()
        eq_id = cursor.lastrowid
        conn.close()
        return EquipmentModel.get_by_id(eq_id), None

    @staticmethod
    def update_equipment(
        equipment_id: int,
        codigo: str,
        nombre: str,
        marca: str,
        modelo: str,
        numero_serie: str,
        area_id: int,
        ubicacion_especifica: str,
        periodicidad_dias: int,
        fecha_ultimo_mantenimiento: str,
        estado: str
    ):
        """Actualiza atributos y periodicidad preventiva del equipo (HU-04)."""
        if not codigo or not codigo.strip():
            return None, "El código del equipo es obligatorio."
        if not nombre or not nombre.strip():
            return None, "El nombre del equipo es obligatorio."
        if not marca or not marca.strip():
            return None, "La marca del equipo es obligatoria."
        if not modelo or not modelo.strip():
            return None, "El modelo del equipo es obligatorio."
        if not numero_serie or not numero_serie.strip():
            return None, "El número de serie es obligatorio."

        try:
            periodicidad = int(periodicidad_dias)
            if periodicidad <= 0:
                return None, "La periodicidad preventiva debe ser mayor a 0 días."
        except (ValueError, TypeError):
            return None, "La periodicidad debe ser un número entero."

        clean_codigo = codigo.strip().upper()
        clean_serie = numero_serie.strip()

        conn = get_db_connection()
        existing = conn.execute("""
            SELECT id FROM equipos 
            WHERE (lower(codigo) = lower(?) OR lower(numero_serie) = lower(?)) AND id != ?;
        """, (clean_codigo, clean_serie, equipment_id)).fetchone()

        if existing:
            conn.close()
            return None, "Otro equipo ya tiene asignado ese código o número de serie."

        conn.execute("""
            UPDATE equipos
            SET codigo = ?, nombre = ?, marca = ?, modelo = ?, numero_serie = ?,
                area_id = ?, ubicacion_especifica = ?, periodicidad_dias = ?,
                fecha_ultimo_mantenimiento = ?, estado = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (
            clean_codigo,
            nombre.strip(),
            marca.strip(),
            modelo.strip(),
            clean_serie,
            area_id,
            (ubicacion_especifica or "").strip(),
            periodicidad,
            fecha_ultimo_mantenimiento or None,
            estado,
            equipment_id
        ))
        conn.commit()
        conn.close()
        return EquipmentModel.get_by_id(equipment_id), None

    @staticmethod
    def toggle_status(equipment_id: int):
        """
        Cambia el estado del equipo entre 'Activo' e 'Inactivo'.
        CONSERVA REFERENCIAS HISTÓRICAS:
        No elimina registros ni desencadena borrados en tickets históricos (HU-04).
        """
        conn = get_db_connection()
        row = conn.execute("SELECT estado, nombre FROM equipos WHERE id = ?;", (equipment_id,)).fetchone()
        if not row:
            conn.close()
            return None, "Equipo no encontrado."

        nuevo_estado = "Inactivo" if row["estado"] == "Activo" else "Activo"
        conn.execute("""
            UPDATE equipos 
            SET estado = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?;
        """, (nuevo_estado, equipment_id))
        conn.commit()
        conn.close()
        return EquipmentModel.get_by_id(equipment_id), None

    @staticmethod
    def get_equipment_history_tickets(equipment_id: int):
        """Retorna todos los tickets asociados a un equipo para auditoría histórica (HU-04)."""
        conn = get_db_connection()
        query = """
            SELECT t.*, s.nombre_completo AS solicitante_nombre, r.nombre_completo AS responsable_nombre
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            WHERE t.equipo_id = ?
            ORDER BY t.id DESC;
        """
        rows = conn.execute(query, (equipment_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class CatalogModel:
    @staticmethod
    def get_categories():
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT clave, valor, descripcion 
            FROM catalogos 
            WHERE tipo = 'categoria_ticket' AND estado = 'Activo'
            ORDER BY valor ASC;
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all(tipo: str = None):
        conn = get_db_connection()
        query = "SELECT * FROM catalogos WHERE 1=1"
        params = []
        if tipo:
            query += " AND tipo = ?"
            params.append(tipo)
        query += " ORDER BY tipo ASC, valor ASC;"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

