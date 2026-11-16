import os
import datetime
from database.db import get_db_connection
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS
from models.sprint_3.ticket import (
    TicketModel as Sprint3TicketModel,
    format_file_size,
    is_allowed_file,
    format_duration
)
from models.sprint_4.reports import ReportsModel


class TicketModel(Sprint3TicketModel):
    """
    Modelo de Tickets extendido para Sprint 4:
    - HU-10: Cierre con solución, cierre sin solución justificado, bloqueo estricto tras cierre,
             y atención nueva relacionada por recurrencia.
    - HU-11: Consulta cronológica completa de trazabilidad, eventos inmutables y control de participantes.
    - HU-12: Reportes ejecutivos, indicadores por situación y exportación CSV autorizada.
    """

    # Matriz extendida de estados (HU-08 y HU-10)
    VALID_TRANSITIONS = {
        "Abierto": ["En Proceso", "Cancelado", "Duplicado"],
        "En Proceso": ["En Espera", "Resuelto", "Cerrado", "Cancelado"],  # Cerrado directo permitido si no hay solución
        "En Espera": ["En Proceso", "Cerrado", "Cancelado"],              # Cerrado directo si no hay solución
        "Resuelto": ["Cerrado", "En Proceso"],
        "Cerrado": [],      # Estado terminal e inmutable tras cierre (HU-10)
        "Cancelado": [],    # Estado terminal
        "Duplicado": []     # Estado terminal
    }

    @staticmethod
    def get_by_id(ticket_id: int):
        conn = get_db_connection()
        query = """
            SELECT t.*, 
                   s.nombre_completo AS solicitante_nombre, s.email AS solicitante_email, s.username AS solicitante_username,
                   r.nombre_completo AS responsable_nombre, r.email AS responsable_email, r.username AS responsable_username,
                   e.codigo AS equipo_codigo, e.nombre AS equipo_nombre, e.marca AS equipo_marca, 
                   e.modelo AS equipo_modelo, e.numero_serie AS equipo_serie, e.estado AS equipo_estado,
                   e.periodicidad_dias AS equipo_periodicidad, e.fecha_ultimo_mantenimiento AS equipo_ultimo_mant,
                   e.ubicacion_especifica AS equipo_ubicacion_esp,
                   COALESCE(a.nombre, ae.nombre) AS area_nombre,
                   COALESCE(a.codigo, ae.codigo) AS area_codigo,
                   tr.codigo AS ticket_relacionado_codigo,
                   tr.titulo AS ticket_relacionado_titulo,
                   tr.estado AS ticket_relacionado_estado,
                   orig.codigo AS ticket_origen_recurrencia_codigo,
                   orig.titulo AS ticket_origen_recurrencia_titulo
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            LEFT JOIN equipos e ON t.equipo_id = e.id
            LEFT JOIN areas a ON t.area_id = a.id
            LEFT JOIN areas ae ON e.area_id = ae.id
            LEFT JOIN tickets tr ON t.ticket_relacionado_id = tr.id
            LEFT JOIN tickets orig ON t.ticket_origen_recurrencia_id = orig.id
            WHERE t.id = ?;
        """
        row = conn.execute(query, (ticket_id,)).fetchone()
        if not row:
            conn.close()
            return None

        ticket = dict(row)

        # Archivos adjuntos con autor
        adj_rows = conn.execute("""
            SELECT ta.*, u.nombre_completo AS autor_nombre, u.rol AS autor_rol
            FROM ticket_adjuntos ta
            LEFT JOIN usuarios u ON ta.usuario_id = u.id
            WHERE ta.ticket_id = ? 
            ORDER BY ta.id ASC;
        """, (ticket_id,)).fetchall()
        ticket["adjuntos"] = [dict(a) for a in adj_rows]

        # Tickets hijos derivados por recurrencia de este ticket (HU-10)
        recurrencias_hijas = conn.execute("""
            SELECT id, codigo, titulo, estado, created_at, prioridad
            FROM tickets
            WHERE ticket_origen_recurrencia_id = ? OR (ticket_relacionado_id = ? AND tipo_relacion = 'Recurrencia')
            ORDER BY id ASC;
        """, (ticket_id, ticket_id)).fetchall()
        ticket["tickets_recurrentes"] = [dict(r) for r in recurrencias_hijas]

        # Métricas de tiempo
        ticket["metricas_tiempo"] = TicketModel.calculate_time_metrics(ticket)

        conn.close()
        return ticket

    # =========================================================================
    # HU-10: RESOLUCIÓN, CIERRE (CON O SIN SOLUCIÓN) Y RECURRENCIA
    # =========================================================================

    @staticmethod
    def resolve_ticket(ticket_id: int, user: dict, solucion_detalle: str) -> tuple[bool, str | None]:
        """
        Registra la solución técnica implementada y pasa el ticket a estado 'Resuelto' (HU-10).
        Criterios:
        - Solución técnica obligatoria y detallada.
        - Actor autorizado: Administrador o Responsable técnico asignado.
        - Bloqueado si el ticket ya está en estado terminal.
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return False, f"Operación no permitida: el ticket #{ticket['codigo']} se encuentra Cerrado y está bloqueado contra modificaciones ordinarias."

        if ticket.get("estado") in ("Cancelado", "Duplicado"):
            return False, f"No se puede resolver un ticket que se encuentra en estado terminal '{ticket['estado']}'."

        # Autorización: Admin o el Responsable técnico asignado
        if user.get("rol") != "Admin" and ticket.get("responsable_id") != user.get("id"):
            return False, "Solo el responsable técnico asignado o el Administrador pueden registrar la resolución técnica."

        clean_solucion = (solucion_detalle or "").strip()
        if not clean_solucion or len(clean_solucion) < 8:
            return False, "Debe registrar obligatoriamente la solución técnica detallada (mínimo 8 caracteres)."

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE tickets
                SET estado = 'Resuelto',
                    solucion_detalle = ?,
                    fecha_resolucion = COALESCE(fecha_resolucion, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (clean_solucion, now_str, ticket_id))

            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario,
                    estado_anterior, estado_nuevo, motivo_detalle, tipo_evento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                user["id"],
                "Resolución Técnica Registrada",
                f"Solución técnica implementada: {clean_solucion}",
                ticket.get("estado"),
                "Resuelto",
                clean_solucion,
                "RESOLUCION"
            ))

            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f"Error al registrar resolución: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def close_ticket(
        ticket_id: int,
        user: dict,
        tipo_cierre: str,
        detalle_o_motivo: str
    ) -> tuple[bool, str | None]:
        """
        Confirma el cierre de un ticket, distinguiendo con o sin solución (HU-10).
        Criterios:
        - Cierre autorizado: Solicitante (confirmación de conformidad) o Administrador.
        - Cierre con solución: Requiere solución documentada y confirmada.
        - Cierre sin solución: Conserva motivos e intentos de diagnóstico previos; exige motivo obligatorio.
        - Estado cerrado: Bloquea modificaciones ordinarias futuras.
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return False, f"El ticket #{ticket['codigo']} ya se encuentra cerrado ({ticket.get('tipo_cierre') or 'definitivo'})."

        # Autorización de cierre (HU-10): Admin o Solicitante del requerimiento
        uid = user.get("id")
        rol = user.get("rol")
        if rol != "Admin" and ticket.get("solicitante_id") != uid:
            return False, "El cierre definitivo de la atención debe ser confirmado por el Solicitante o un Administrador."

        clean_texto = (detalle_o_motivo or "").strip()

        if tipo_cierre not in ("Con Solución", "Sin Solución"):
            return False, "El tipo de cierre debe ser 'Con Solución' o 'Sin Solución'."

        solucion = ticket.get("solucion_detalle")
        motivo_sin_sol = None

        if tipo_cierre == "Con Solución":
            if clean_texto:
                solucion = clean_texto
            if not solucion:
                return False, "Debe registrar la solución técnica aplicada para cerrar el ticket con solución."
        else:
            # Cierre sin solución justificado
            if not clean_texto or len(clean_texto) < 8:
                return False, "Debe registrar obligatoriamente la justificación/motivo de por qué el ticket se cierra sin solución (mínimo 8 caracteres)."
            motivo_sin_sol = clean_texto

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            old_status = ticket.get("estado")

            cursor.execute("""
                UPDATE tickets
                SET estado = 'Cerrado',
                    tipo_cierre = ?,
                    solucion_detalle = ?,
                    motivo_sin_solucion = ?,
                    fecha_cierre = ?,
                    fecha_resolucion = COALESCE(fecha_resolucion, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (tipo_cierre, solucion, motivo_sin_sol, now_str, now_str, ticket_id))

            if tipo_cierre == "Con Solución":
                accion_lbl = "Cierre Definitivo Con Solución"
                comentario_hist = f"Cierre confirmado con solución satisfactoria: {solucion}"
                evento_tag = "CIERRE_CON_SOLUCION"
            else:
                accion_lbl = "Cierre Sin Solución (Justificado)"
                comentario_hist = f"Ticket cerrado sin solución técnica. Justificación: {motivo_sin_sol}"
                evento_tag = "CIERRE_SIN_SOLUCION"

            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario,
                    estado_anterior, estado_nuevo, motivo_detalle, tipo_evento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                user["id"],
                accion_lbl,
                comentario_hist,
                old_status,
                "Cerrado",
                motivo_sin_sol or solucion,
                evento_tag
            ))

            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f"Error al cerrar ticket: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def create_recurrence(
        ticket_id: int,
        user: dict,
        situacion_falla: str,
        prioridad: str = None,
        detector_nombre: str = None
    ) -> tuple[dict | None, str | None]:
        """
        Crea una nueva atención relacionada cuando reaparece el problema en un ticket cerrado o resuelto (HU-10).
        Criterios:
        - El ticket original debe estar Cerrado o Resuelto.
        - Persona autorizada: Solicitante original, Responsable o Admin.
        - Vinculación bidireccional y folio único nuevo correlativo.
        - Conserva equipo, área, ubicación y categoría originales.
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket origen no encontrado."

        if ticket.get("estado") not in ("Cerrado", "Resuelto"):
            return None, f"Solo se puede reportar recurrencia en atenciones que se encuentren en estado 'Cerrado' o 'Resuelto' (estado actual: '{ticket['estado']}')."

        if not TicketModel.user_can_view(user, ticket):
            return None, "No cuentas con autorización para reportar recurrencia en esta atención."

        clean_falla = (situacion_falla or "").strip()
        if not clean_falla or len(clean_falla) < 8:
            return None, "Debe describir la situación de la recurrencia o falla reaparecida (mínimo 8 caracteres)."

        # Crear el nuevo ticket con folio único
        nuevo_titulo = f"[Recurrencia] {ticket['titulo']}"
        solicitante_id = user["id"] if user["rol"] == "Usuario" else ticket["solicitante_id"]
        prio = prioridad or ticket["prioridad"]
        det_nombre = (detector_nombre or "").strip() or user.get("nombre_completo") or "Personal de Planta"

        new_t, err = TicketModel.create_ticket(
            titulo=nuevo_titulo,
            situacion_problema=f"Falla recurrente derivada del ticket #{ticket['codigo']}.\nDetalle: {clean_falla}",
            detector_nombre=det_nombre,
            equipo_id=ticket.get("equipo_id"),
            categoria=ticket.get("categoria"),
            prioridad=prio,
            solicitante_id=solicitante_id,
            responsable_id=ticket.get("responsable_id") if user["rol"] == "Admin" else None,
            ubicacion_equipo=ticket.get("ubicacion_equipo")
        )
        if err or not new_t:
            return None, f"Error al generar la nueva atención por recurrencia: {err}"

        # Actualizar campos de relación por recurrencia
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Vincular en el nuevo ticket
            cursor.execute("""
                UPDATE tickets
                SET es_recurrencia = 1,
                    ticket_relacionado_id = ?,
                    ticket_origen_recurrencia_id = ?,
                    tipo_relacion = 'Recurrencia'
                WHERE id = ?;
            """, (ticket_id, ticket_id, new_t["id"]))

            # Registrar evento en el historial del nuevo ticket
            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario,
                    estado_anterior, estado_nuevo, motivo_detalle, tipo_evento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                new_t["id"],
                user["id"],
                "Atención Aperturada por Recurrencia",
                f"Atención generada automáticamente por recurrencia del ticket #{ticket['codigo']} ({ticket.get('tipo_cierre', 'Cerrado')}).",
                None,
                "Abierto",
                clean_falla,
                "RECURRENCIA_CREADA"
            ))

            # Registrar evento en el historial del ticket original
            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario,
                    estado_anterior, estado_nuevo, motivo_detalle, tipo_evento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                user["id"],
                "Nueva Atención Relacionada por Recurrencia",
                f"Se detectó recurrencia de la avería. Se aperturó la nueva atención #{new_t['codigo']}.",
                ticket.get("estado"),
                ticket.get("estado"),
                f"Nueva atención folio: {new_t['codigo']}",
                "RECURRENCIA_ORIGEN"
            ))

            conn.commit()
            return TicketModel.get_by_id(new_t["id"]), None
        except Exception as e:
            conn.rollback()
            return None, f"Error al vincular recurrencia: {str(e)}"
        finally:
            conn.close()

    # =========================================================================
    # BLOQUEO ESTRICTO DE CAMBIOS ORDINARIOS TRAS CIERRE (HU-10)
    # =========================================================================

    @staticmethod
    def update_status(
        ticket_id: int,
        new_status: str,
        user: dict,
        comentario: str = None,
        ticket_relacionado_id: int = None
    ) -> tuple[bool, str | None]:
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return False, f"Operación no permitida: el ticket #{ticket['codigo']} se encuentra Cerrado ({ticket.get('tipo_cierre') or 'definitivo'}) y está bloqueado contra modificaciones ordinarias (HU-10)."

        return Sprint3TicketModel.update_status(ticket_id, new_status, user, comentario, ticket_relacionado_id)

    @staticmethod
    def reassign_responsable(
        ticket_id: int,
        new_responsable_id: int | None,
        admin_user: dict,
        motivo: str = None,
        nueva_categoria: str = None,
        nueva_prioridad: str = None
    ) -> tuple[bool, str | None]:
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return False, f"Operación no permitida: el ticket #{ticket['codigo']} se encuentra Cerrado y no admite reasignación técnica ordinaria (HU-10)."

        return Sprint3TicketModel.reassign_responsable(ticket_id, new_responsable_id, admin_user, motivo, nueva_categoria, nueva_prioridad)

    @staticmethod
    def add_comment(
        ticket_id: int,
        user: dict,
        comentario: str,
        archivo=None
    ) -> tuple[dict | None, str | None]:
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return None, f"Operación no permitida: el ticket #{ticket['codigo']} se encuentra Cerrado y no admite nuevas notas técnicas ordinarias (HU-10)."

        return Sprint3TicketModel.add_comment(ticket_id, user, comentario, archivo=archivo)

    @staticmethod
    def add_attachment_to_ticket(ticket_id: int, user: dict, file_obj) -> tuple[dict | None, str | None]:
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket no encontrado."

        if ticket.get("estado") == "Cerrado":
            return None, f"Operación no permitida: el ticket #{ticket['codigo']} se encuentra Cerrado y no admite carga de nuevas evidencias (HU-10)."

        return Sprint3TicketModel.add_attachment_to_ticket(ticket_id, user, file_obj)

    # =========================================================================
    # HU-11: AUDITORÍA Y TRAZABILIDAD CRONOLÓGICA COMPLETA
    # =========================================================================

    @staticmethod
    def get_full_audit_trail(ticket_id: int, user: dict) -> tuple[list[dict] | None, str | None]:
        """
        Retorna la línea de tiempo completa y cronológica de todo lo ocurrido en el ticket (HU-11).
        Criterios:
        - Respetar permisos del ticket (solo participantes autorizados).
        - Acción, momento (timestamp inmutable) y persona identificable (id, nombre, rol).
        - Inmutabilidad estricta (no existe edición ni borrado).
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket no encontrado."

        if not TicketModel.user_can_view(user, ticket):
            return None, "403 Forbidden: No cuentas con autorización para consultar la trazabilidad de este ticket."

        conn = get_db_connection()
        query = """
            SELECT th.*,
                   u.nombre_completo AS autor_nombre,
                   u.nombre_completo AS usuario_nombre,
                   u.email AS autor_email,
                   u.email AS usuario_email,
                   u.rol AS autor_rol,
                   u.rol AS usuario_rol,
                   ra.nombre_completo AS resp_anterior_nombre,
                   rn.nombre_completo AS resp_nuevo_nombre
            FROM ticket_historial th
            JOIN usuarios u ON th.usuario_id = u.id
            LEFT JOIN usuarios ra ON th.responsable_anterior_id = ra.id
            LEFT JOIN usuarios rn ON th.responsable_nuevo_id = rn.id
            WHERE th.ticket_id = ?
            ORDER BY th.created_at ASC, th.id ASC;
        """
        rows = conn.execute(query, (ticket_id,)).fetchall()
        conn.close()

        trail = [dict(r) for r in rows]
        return trail, None

    @staticmethod
    def attempt_delete_or_edit_history(history_id: int) -> tuple[bool, str]:
        """Demuestra el criterio de inmutabilidad estricta: prohíbe edición o borrado de eventos de auditoría (HU-11)."""
        return False, "Violación de integridad: Los registros de trazabilidad y auditoría son inmutables (append-only) y no admiten edición ni eliminación ordinaria."

    # =========================================================================
    # HU-12: REPORTES, INDICADORES Y EXPORTACIÓN CSV
    # =========================================================================

    @staticmethod
    def get_executive_report(user: dict, filters: dict = None) -> dict:
        """Visualiza resumen de tickets, conteos por situaciones y preventivos (HU-12)."""
        return ReportsModel.get_summary(user, filters)

    @staticmethod
    def export_tickets_to_csv(user: dict, filters: dict = None) -> str:
        """Exporta información autorizada de tickets en formato CSV compatible con Excel (HU-12)."""
        return ReportsModel.export_csv(user, filters)
