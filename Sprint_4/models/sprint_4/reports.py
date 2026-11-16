import csv
import io
import datetime
from database.db import get_db_connection
from models.sprint_2.equipment import EquipmentModel


def format_minutes_to_duration(total_minutes: int) -> str:
    if total_minutes is None or total_minutes < 0:
        return "N/D"
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours < 24:
        return f"{hours}h {mins}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h {mins}m"


class ReportsModel:
    """Motor de reportes ejecutivos, indicadores analíticos y exportación CSV autorizada (HU-12)."""

    @staticmethod
    def get_summary(user: dict, filters: dict = None) -> dict:
        """
        Calcula resumen ejecutivo de tickets e indicadores con filtros combinables (HU-12).
        Criterios:
        - Conteos según filtros (estado, prioridad, categoría, área, equipo, fechas).
        - Respetar permisos (Admin visualiza global; Responsable visualiza su alcance asignado).
        - Distinguir situaciones (con solución, sin solución justificada, recurrencias, esperas, cancelados).
        - Mantenimientos preventivos próximos y vencidos (HU-04 + HU-12).
        """
        filters = filters or {}
        conn = get_db_connection()

        role = user.get("rol")
        uid = user.get("id")

        where_clauses = ["1=1"]
        params = []

        # Control de permisos por rol (HU-02 y HU-12)
        if role == "Admin":
            pass
        elif role == "Responsable":
            where_clauses.append("(t.responsable_id = ? OR t.solicitante_id = ?)")
            params.extend([uid, uid])
        elif role == "Usuario":
            where_clauses.append("t.solicitante_id = ?")
            params.append(uid)
        else:
            conn.close()
            return {}

        # Filtros opcionales
        if filters.get("estado"):
            where_clauses.append("t.estado = ?")
            params.append(filters["estado"])

        if filters.get("prioridad"):
            where_clauses.append("t.prioridad = ?")
            params.append(filters["prioridad"])

        if filters.get("categoria"):
            where_clauses.append("t.categoria = ?")
            params.append(filters["categoria"])

        if filters.get("area_id"):
            try:
                where_clauses.append("(t.area_id = ? OR e.area_id = ?)")
                a_id = int(filters["area_id"])
                params.extend([a_id, a_id])
            except (ValueError, TypeError):
                pass

        if filters.get("equipo_id"):
            try:
                where_clauses.append("t.equipo_id = ?")
                params.append(int(filters["equipo_id"]))
            except (ValueError, TypeError):
                pass

        if filters.get("responsable_id") and role == "Admin":
            try:
                where_clauses.append("t.responsable_id = ?")
                params.append(int(filters["responsable_id"]))
            except (ValueError, TypeError):
                pass

        if filters.get("tipo_cierre"):
            where_clauses.append("t.tipo_cierre = ?")
            params.append(filters["tipo_cierre"])

        if filters.get("es_recurrencia") in (1, "1", True, "true"):
            where_clauses.append("t.es_recurrencia = 1")

        if filters.get("fecha_desde"):
            where_clauses.append("t.created_at >= ?")
            params.append(f"{filters['fecha_desde']} 00:00:00")

        if filters.get("fecha_hasta"):
            where_clauses.append("t.created_at <= ?")
            params.append(f"{filters['fecha_hasta']} 23:59:59")

        where_sql = " AND ".join(where_clauses)

        base_query = f"""
            SELECT t.*,
                   s.nombre_completo AS solicitante_nombre,
                   r.nombre_completo AS responsable_nombre,
                   e.codigo AS equipo_codigo, e.nombre AS equipo_nombre,
                   COALESCE(a.nombre, ae.nombre) AS area_nombre,
                   tr.codigo AS ticket_relacionado_codigo
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            LEFT JOIN equipos e ON t.equipo_id = e.id
            LEFT JOIN areas a ON t.area_id = a.id
            LEFT JOIN areas ae ON e.area_id = ae.id
            LEFT JOIN tickets tr ON t.ticket_relacionado_id = tr.id
            WHERE {where_sql}
            ORDER BY t.id DESC;
        """
        rows = [dict(r) for r in conn.execute(base_query, params).fetchall()]

        # Conteos y agrupaciones
        total_tickets = len(rows)

        estados = {"Abierto": 0, "En Proceso": 0, "En Espera": 0, "Resuelto": 0, "Cerrado": 0, "Cancelado": 0, "Duplicado": 0}
        prioridades = {"Baja": 0, "Media": 0, "Alta": 0, "Urgente": 0}
        categorias = {}
        situaciones = {
            "con_solucion": 0,
            "cerrados_con_solucion": 0,
            "sin_solucion": 0,
            "cerrados_sin_solucion": 0,
            "recurrencias": 0,
            "en_espera": 0,
            "duplicados": 0,
            "cancelados": 0,
            "resueltos": 0
        }

        lead_times = []
        espera_times = []
        neto_times = []

        fmt = "%Y-%m-%d %H:%M:%S"
        now_dt = datetime.datetime.now()

        for t in rows:
            est = t.get("estado")
            if est in estados:
                estados[est] += 1

            prio = t.get("prioridad")
            if prio in prioridades:
                prioridades[prio] += 1

            cat = t.get("categoria") or "Sin Categoría"
            categorias[cat] = categorias.get(cat, 0) + 1

            # Situaciones distintivas (HU-10 y HU-12)
            if t.get("tipo_cierre") == "Con Solución":
                situaciones["con_solucion"] += 1
                situaciones["cerrados_con_solucion"] += 1
            elif t.get("tipo_cierre") == "Sin Solución":
                situaciones["sin_solucion"] += 1
                situaciones["cerrados_sin_solucion"] += 1

            if t.get("es_recurrencia") == 1 or t.get("tipo_relacion") == "Recurrencia":
                situaciones["recurrencias"] += 1

            if est == "En Espera":
                situaciones["en_espera"] += 1
            elif est == "Duplicado":
                situaciones["duplicados"] += 1
            elif est == "Cancelado":
                situaciones["cancelados"] += 1
            elif est == "Resuelto":
                situaciones["resueltos"] += 1

            # Métricas de tiempos
            try:
                c_dt = datetime.datetime.strptime(str(t["created_at"])[:19], fmt)
                end_dt = now_dt
                if t.get("fecha_cierre"):
                    end_dt = datetime.datetime.strptime(str(t["fecha_cierre"])[:19], fmt)
                elif t.get("fecha_resolucion"):
                    end_dt = datetime.datetime.strptime(str(t["fecha_resolucion"])[:19], fmt)

                l_min = max(0, int((end_dt - c_dt).total_seconds() / 60))
                w_min = t.get("tiempo_espera_minutos") or 0
                n_min = max(0, l_min - w_min)

                t["tiempo_total_minutos"] = l_min
                t["tiempo_espera_minutos"] = w_min
                t["tiempo_neto_minutos"] = n_min

                lead_times.append(l_min)
                espera_times.append(w_min)
                neto_times.append(n_min)
            except Exception:
                t["tiempo_total_minutos"] = 0
                t["tiempo_espera_minutos"] = 0
                t["tiempo_neto_minutos"] = 0

        avg_lead = int(sum(lead_times) / len(lead_times)) if lead_times else 0
        avg_wait = int(sum(espera_times) / len(espera_times)) if espera_times else 0
        avg_neto = int(sum(neto_times) / len(neto_times)) if neto_times else 0

        # Mantenimiento preventivo de equipos (HU-04 y HU-12)
        equipos_preventivos = ReportsModel.get_preventive_maintenance_status(conn)

        conn.close()

        return {
            "total_tickets": total_tickets,
            "estados": estados,
            "conteo_estados": estados,
            "prioridades": prioridades,
            "conteo_prioridades": prioridades,
            "categorias": categorias,
            "conteo_categorias": categorias,
            "situaciones": situaciones,
            "tiempos_promedio": {
                "lead_time_minutos": avg_lead,
                "lead_time_texto": format_minutes_to_duration(avg_lead),
                "tiempo_espera_minutos": avg_wait,
                "tiempo_espera_texto": format_minutes_to_duration(avg_wait),
                "tiempo_neto_minutos": avg_neto,
                "tiempo_neto_texto": format_minutes_to_duration(avg_neto),
            },
            "preventivo": equipos_preventivos,
            "mantenimiento_preventivo": equipos_preventivos,
            "tickets": rows
        }

    @staticmethod
    def get_preventive_maintenance_status(conn=None) -> dict:
        """Calcula el estado del mantenimiento preventivo próximo y vencido de todos los equipos activos (HU-04, HU-12)."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True

        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, a.nombre AS area_nombre, a.codigo AS area_codigo
            FROM equipos e
            JOIN areas a ON e.area_id = a.id
            WHERE e.estado = 'Activo'
            ORDER BY e.codigo ASC;
        """)
        equipos = [dict(r) for r in cursor.fetchall()]

        hoy = datetime.date.today()
        al_dia_count = 0
        proximo_count = 0
        vencido_count = 0
        lista_alertas = []

        for eq in equipos:
            calc = EquipmentModel.calculate_maintenance_info(
                eq.get("fecha_ultimo_mantenimiento"),
                eq.get("periodicidad_dias")
            )
            eq["dias_restantes"] = calc.get("dias_restantes")
            eq["proximo_mantenimiento"] = calc.get("proximo")
            eq["estado_mantenimiento"] = calc.get("status_texto")
            eq["alerta_texto"] = calc.get("status_texto")

            dias = calc.get("dias_restantes")
            if dias is None:
                al_dia_count += 1
                eq["semaforo"] = "al_dia"
            elif dias < 0:
                vencido_count += 1
                eq["semaforo"] = "vencido"
                lista_alertas.append(eq)
            elif dias <= 7:
                proximo_count += 1
                eq["semaforo"] = "proximo"
                lista_alertas.append(eq)
            else:
                al_dia_count += 1
                eq["semaforo"] = "al_dia"

        if should_close:
            conn.close()

        totales = {
            "al_dia": al_dia_count,
            "proximo": proximo_count,
            "vencido": vencido_count,
            "total_equipos": len(equipos)
        }

        return {
            "totales": totales,
            "al_dia_total": al_dia_count,
            "proximo_total": proximo_count,
            "vencido_total": vencido_count,
            "total_equipos_activos": len(equipos),
            "alertas": lista_alertas,
            "equipos": equipos
        }

    @staticmethod
    def export_csv(user: dict, filters: dict = None) -> str:
        """
        Genera archivo CSV conforme al estándar RFC 4180 codificado con BOM UTF-8 (HU-12).
        Permite apertura transparente en Excel y clientes de análisis.
        """
        summary_data = ReportsModel.get_summary(user, filters)
        tickets = summary_data.get("tickets", [])

        output = io.StringIO()
        # Agregar BOM para que Excel en Windows interprete acentos y caracteres especiales automáticamente
        output.write("\ufeff")

        writer = csv.writer(output, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

        # Encabezados de columnas normalizadas
        headers = [
            "Folio",
            "Título",
            "Situación Problema",
            "Categoría",
            "Prioridad",
            "Estado Actual",
            "Tipo de Cierre",
            "Solución / Justificación Técnica",
            "Motivo Sin Solución",
            "Es Recurrencia",
            "Folio Ticket Relacionado / Origen",
            "Tipo Relación",
            "Equipo Código",
            "Equipo Nombre",
            "Área Industrial",
            "Solicitante (Creador)",
            "Responsable Técnico",
            "Fecha de Registro",
            "Fecha de Resolución",
            "Fecha de Cierre",
            "Tiempo Total Lead Time (min)",
            "Tiempo en Espera (min)",
            "Tiempo Neto Atención (min)"
        ]
        writer.writerow(headers)

        for t in tickets:
            writer.writerow([
                t.get("codigo") or "",
                t.get("titulo") or "",
                (t.get("situacion_problema") or t.get("descripcion") or "").replace("\r\n", " ").replace("\n", " "),
                t.get("categoria") or "",
                t.get("prioridad") or "",
                t.get("estado") or "",
                t.get("tipo_cierre") or "N/A",
                (t.get("solucion_detalle") or "").replace("\r\n", " ").replace("\n", " "),
                (t.get("motivo_sin_solucion") or "").replace("\r\n", " ").replace("\n", " "),
                "Sí" if t.get("es_recurrencia") == 1 else "No",
                t.get("ticket_relacionado_codigo") or "",
                t.get("tipo_relacion") or "",
                t.get("equipo_codigo") or "N/A",
                t.get("equipo_nombre") or "N/A",
                t.get("area_nombre") or "N/A",
                t.get("solicitante_nombre") or "",
                t.get("responsable_nombre") or "Sin Asignar",
                str(t.get("created_at") or "")[:19],
                str(t.get("fecha_resolucion") or "")[:19],
                str(t.get("fecha_cierre") or "")[:19],
                t.get("tiempo_total_minutos", 0),
                t.get("tiempo_espera_minutos", 0),
                t.get("tiempo_neto_minutos", 0)
            ])

        return output.getvalue()
