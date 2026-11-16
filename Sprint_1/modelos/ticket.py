import os
import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from database.db import get_db_connection
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS

def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def is_allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def format_duration(total_minutes: int) -> str:
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

class TicketModel:
    # Matriz estricta de transiciones de estado permitidas (HU-08: Máquina de Estados Finita)
    VALID_TRANSITIONS = {
        "Abierto": ["En Proceso", "Cancelado", "Duplicado"],
        "En Proceso": ["En Espera", "Resuelto", "Cancelado"],
        "En Espera": ["En Proceso", "Cancelado"],
        "Resuelto": ["Cerrado", "En Proceso"],
        "Cerrado": [],      # Estado terminal
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
                   tr.titulo AS ticket_relacionado_titulo
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            LEFT JOIN equipos e ON t.equipo_id = e.id
            LEFT JOIN areas a ON t.area_id = a.id
            LEFT JOIN areas ae ON e.area_id = ae.id
            LEFT JOIN tickets tr ON t.ticket_relacionado_id = tr.id
            WHERE t.id = ?;
        """
        row = conn.execute(query, (ticket_id,)).fetchone()
        if not row:
            conn.close()
            return None

        ticket = dict(row)
        
        # Recuperar archivos adjuntos con autor (HU-05 y HU-09)
        adj_rows = conn.execute("""
            SELECT ta.*, u.nombre_completo AS autor_nombre, u.rol AS autor_rol
            FROM ticket_adjuntos ta
            LEFT JOIN usuarios u ON ta.usuario_id = u.id
            WHERE ta.ticket_id = ? 
            ORDER BY ta.id ASC;
        """, (ticket_id,)).fetchall()
        ticket["adjuntos"] = [dict(a) for a in adj_rows]

        # Calcular métricas de tiempo (HU-08)
        ticket["metricas_tiempo"] = TicketModel.calculate_time_metrics(ticket)

        conn.close()
        return ticket

    @staticmethod
    def calculate_time_metrics(ticket: dict) -> dict:
        """Calcula el tiempo total transcurrido, tiempo en espera y tiempo neto de atención (HU-08)."""
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            created_str = str(ticket.get("created_at") or "")[:19]
            if not created_str:
                return {}
            
            created_dt = datetime.datetime.strptime(created_str, fmt)
            
            # Fin del tiempo: cierre, resolución o ahora
            end_dt = datetime.datetime.now()
            if ticket.get("fecha_cierre"):
                end_dt = datetime.datetime.strptime(str(ticket["fecha_cierre"])[:19], fmt)
            elif ticket.get("fecha_resolucion"):
                end_dt = datetime.datetime.strptime(str(ticket["fecha_resolucion"])[:19], fmt)

            total_min = max(0, int((end_dt - created_dt).total_seconds() / 60))
            espera_min = ticket.get("tiempo_espera_minutos") or 0
            
            # Si actualmente sigue 'En Espera', sumar tiempo transcurrido de la espera actual
            if ticket.get("estado") == "En Espera" and ticket.get("ultima_fecha_espera"):
                try:
                    ult_esp = datetime.datetime.strptime(str(ticket["ultima_fecha_espera"])[:19], fmt)
                    espera_min += max(0, int((datetime.datetime.now() - ult_esp).total_seconds() / 60))
                except Exception:
                    pass

            neto_min = max(0, total_min - espera_min)

            return {
                "tiempo_total_minutos": total_min,
                "tiempo_total_texto": format_duration(total_min),
                "tiempo_espera_minutos": espera_min,
                "tiempo_espera_texto": format_duration(espera_min),
                "tiempo_neto_minutos": neto_min,
                "tiempo_neto_texto": format_duration(neto_min)
            }
        except Exception:
            return {
                "tiempo_total_texto": "N/D",
                "tiempo_espera_texto": "0 min",
                "tiempo_neto_texto": "N/D"
            }

    @staticmethod
    def get_by_codigo(codigo: str):
        if not codigo:
            return None
        conn = get_db_connection()
        query = """
            SELECT t.*, 
                   s.nombre_completo AS solicitante_nombre, s.email AS solicitante_email,
                   r.nombre_completo AS responsable_nombre, r.email AS responsable_email,
                   e.codigo AS equipo_codigo, e.nombre AS equipo_nombre, e.marca AS equipo_marca,
                   e.modelo AS equipo_modelo, e.numero_serie AS equipo_serie, e.estado AS equipo_estado,
                   COALESCE(a.nombre, ae.nombre) AS area_nombre
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            LEFT JOIN equipos e ON t.equipo_id = e.id
            LEFT JOIN areas a ON t.area_id = a.id
            LEFT JOIN areas ae ON e.area_id = ae.id
            WHERE lower(t.codigo) = lower(?);
        """
        row = conn.execute(query, (codigo.strip(),)).fetchone()
        if not row:
            conn.close()
            return None

        ticket = dict(row)
        adj_rows = conn.execute("""
            SELECT ta.*, u.nombre_completo AS autor_nombre, u.rol AS autor_rol
            FROM ticket_adjuntos ta
            LEFT JOIN usuarios u ON ta.usuario_id = u.id
            WHERE ta.ticket_id = ? 
            ORDER BY ta.id ASC;
        """, (ticket["id"],)).fetchall()
        ticket["adjuntos"] = [dict(a) for a in adj_rows]
        ticket["metricas_tiempo"] = TicketModel.calculate_time_metrics(ticket)
        conn.close()
        return ticket

    @staticmethod
    def get_tickets_for_user(
        user: dict,
        search: str = None,
        folio: str = None,
        equipo_id: int = None,
        solicitante_id: int = None,
        responsable_id: int = None,
        area_id: int = None,
        prioridad: str = None,
        estado: str = None,
        categoria: str = None
    ):
        """
        Retorna la lista de tickets aplicando estrictamente el control de acceso por rol 
        y participación (HU-02 y HU-06), más filtros avanzados combinables:
        - Admin: acceso a todos los tickets y puede filtrar por cualquier participante.
        - Responsable: solo tickets donde es el responsable técnico o solicitante.
        - Usuario: exclusivamente tickets creados por él mismo.
        """
        conn = get_db_connection()
        query = """
            SELECT t.*, 
                   s.nombre_completo AS solicitante_nombre,
                   r.nombre_completo AS responsable_nombre,
                   e.codigo AS equipo_codigo, e.nombre AS equipo_nombre,
                   COALESCE(a.nombre, ae.nombre) AS area_nombre,
                   (SELECT COUNT(*) FROM ticket_adjuntos ta WHERE ta.ticket_id = t.id) AS total_adjuntos
            FROM tickets t
            JOIN usuarios s ON t.solicitante_id = s.id
            LEFT JOIN usuarios r ON t.responsable_id = r.id
            LEFT JOIN equipos e ON t.equipo_id = e.id
            LEFT JOIN areas a ON t.area_id = a.id
            LEFT JOIN areas ae ON e.area_id = ae.id
            WHERE 1=1
        """
        params = []
        role = user.get("rol")
        uid = user.get("id")

        # Filtro estricto de visibilidad por rol y participación (HU-02 y HU-06)
        if role == "Admin":
            pass  # Admin ve todo
        elif role == "Responsable":
            query += " AND (t.responsable_id = ? OR t.solicitante_id = ?)"
            params.extend([uid, uid])
        elif role == "Usuario":
            query += " AND t.solicitante_id = ?"
            params.append(uid)
        else:
            conn.close()
            return []

        # Filtro: Búsqueda por folio específico o general (HU-06)
        if folio and folio.strip():
            query += " AND lower(t.codigo) LIKE ?"
            params.append(f"%{folio.strip().lower()}%")

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query += """ AND (
                lower(t.codigo) LIKE ? OR 
                lower(t.titulo) LIKE ? OR 
                lower(t.descripcion) LIKE ? OR 
                lower(COALESCE(t.situacion_problema, '')) LIKE ? OR 
                lower(COALESCE(e.codigo, '')) LIKE ? OR 
                lower(COALESCE(e.nombre, '')) LIKE ? OR 
                lower(COALESCE(t.ubicacion_equipo, '')) LIKE ?
            )"""
            params.extend([term, term, term, term, term, term, term])

        # Filtro por equipo (HU-06)
        if equipo_id:
            try:
                eq_val = int(equipo_id)
                query += " AND t.equipo_id = ?"
                params.append(eq_val)
            except (ValueError, TypeError):
                pass

        # Filtro por solicitante (HU-06)
        if solicitante_id and role in ("Admin", "Responsable"):
            try:
                sol_val = int(solicitante_id)
                query += " AND t.solicitante_id = ?"
                params.append(sol_val)
            except (ValueError, TypeError):
                pass

        # Filtro por responsable (HU-06: para Admin)
        if responsable_id and role == "Admin":
            try:
                resp_val = int(responsable_id)
                query += " AND t.responsable_id = ?"
                params.append(resp_val)
            except (ValueError, TypeError):
                pass

        # Filtro por área (HU-06)
        if area_id:
            try:
                ar_val = int(area_id)
                query += " AND (t.area_id = ? OR e.area_id = ?)"
                params.extend([ar_val, ar_val])
            except (ValueError, TypeError):
                pass

        # Filtro por prioridad (HU-06)
        if prioridad and prioridad in ('Baja', 'Media', 'Alta', 'Urgente'):
            query += " AND t.prioridad = ?"
            params.append(prioridad)

        # Filtro por estado (HU-06 y HU-08)
        if estado and estado in ('Abierto', 'En Proceso', 'En Espera', 'Resuelto', 'Cerrado', 'Cancelado', 'Duplicado'):
            query += " AND t.estado = ?"
            params.append(estado)

        if categoria:
            query += " AND t.categoria = ?"
            params.append(categoria)

        query += " ORDER BY t.id DESC;"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def user_can_view(user: dict, ticket: dict) -> bool:
        """Verifica si el participante tiene autorización para consultar el ticket (HU-02 y HU-06)."""
        if not user or not ticket:
            return False
        role = user.get("rol")
        uid = user.get("id")
        if role == "Admin":
            return True
        if role == "Responsable":
            return ticket.get("responsable_id") == uid or ticket.get("solicitante_id") == uid
        if role == "Usuario":
            return ticket.get("solicitante_id") == uid
        return False

    @staticmethod
    def user_can_modify(user: dict, ticket: dict) -> bool:
        """Verifica si el usuario tiene permiso para actualizar estado según su rol (HU-02 y HU-08)."""
        if not user or not ticket:
            return False
        role = user.get("rol")
        uid = user.get("id")
        if role == "Admin":
            return True
        if role == "Responsable":
            return ticket.get("responsable_id") == uid
        if role == "Usuario":
            # El solicitante puede dar conformidad de Cierre o Cancelar si sigue Abierto
            return ticket.get("solicitante_id") == uid
        return False

    @staticmethod
    def generate_ticket_code(conn) -> str:
        """Genera un folio consecutivo único: TK-YYYY-NNN (HU-05)."""
        year = datetime.datetime.now().year
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets;")
        count = cursor.fetchone()[0] + 1
        codigo = f"TK-{year}-{count:03d}"
        
        while True:
            row = cursor.execute("SELECT 1 FROM tickets WHERE codigo = ?;", (codigo,)).fetchone()
            if not row:
                break
            count += 1
            codigo = f"TK-{year}-{count:03d}"
        return codigo

    @staticmethod
    def create_ticket(
        titulo: str,
        situacion_problema: str,
        detector_nombre: str,
        equipo_id: int,
        categoria: str,
        prioridad: str,
        solicitante_id: int,
        responsable_id: int = None,
        descripcion: str = None,
        ubicacion_equipo: str = None,
        archivos: list = None
    ) -> tuple[dict | None, str | None]:
        """Registra una solicitud relacionada obligatoriamente con un equipo activo (HU-05)."""
        clean_titulo = (titulo or "").strip()
        clean_situacion = (situacion_problema or "").strip()
        clean_detector = (detector_nombre or "").strip()
        clean_categoria = (categoria or "").strip()
        clean_prioridad = (prioridad or "").strip()

        if not clean_titulo:
            return None, "El título o resumen de la solicitud es obligatorio."
        if len(clean_titulo) < 5:
            return None, "El título debe contener al menos 5 caracteres descriptivos."

        if not clean_situacion:
            return None, "La descripción de la situación o falla detectada es obligatoria."
        if len(clean_situacion) < 10:
            return None, "La descripción de la situación debe contener al menos 10 caracteres."

        if not clean_detector:
            return None, "Debe especificar el nombre o cargo de quién detectó la falla/situación."

        if not equipo_id:
            return None, "Debe seleccionar el equipo activo relacionado con la solicitud."

        if clean_prioridad not in ('Baja', 'Media', 'Alta', 'Urgente'):
            return None, "La prioridad seleccionada no es válida (debe ser Baja, Media, Alta o Urgente)."

        if not clean_categoria:
            clean_categoria = "Mantenimiento General"

        conn = get_db_connection()
        try:
            # Validación de Equipo Activo (HU-05)
            eq_row = conn.execute("SELECT id, codigo, nombre, area_id, estado, ubicacion_especifica FROM equipos WHERE id = ?;", (equipo_id,)).fetchone()
            if not eq_row:
                return None, "El equipo seleccionado no existe en el catálogo."
            if eq_row["estado"] != "Activo":
                return None, f"El equipo '{eq_row['nombre']}' ({eq_row['codigo']}) se encuentra {eq_row['estado'].upper()} y no puede ser seleccionado para nuevos tickets."

            area_id = eq_row["area_id"]
            ubicacion_final = ubicacion_equipo or eq_row["ubicacion_especifica"] or ""

            # Generación de folio único (HU-05)
            codigo = TicketModel.generate_ticket_code(conn)

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tickets (
                    codigo, titulo, descripcion, situacion_problema, detector_nombre,
                    categoria, prioridad, estado, solicitante_id, responsable_id,
                    equipo_id, area_id, ubicacion_equipo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Abierto', ?, ?, ?, ?, ?);
            """, (
                codigo,
                clean_titulo,
                descripcion.strip() if descripcion else clean_situacion,
                clean_situacion,
                clean_detector,
                clean_categoria,
                clean_prioridad,
                solicitante_id,
                responsable_id,
                equipo_id,
                area_id,
                ubicacion_final
            ))
            ticket_id = cursor.lastrowid

            # Procesamiento de evidencias adjuntas (<= 10 MB) (HU-05)
            adjuntos_guardados = 0
            if archivos:
                for file_obj in archivos:
                    if file_obj and hasattr(file_obj, "filename") and file_obj.filename:
                        orig_name = os.path.basename(file_obj.filename)
                        if not is_allowed_file(orig_name):
                            conn.rollback()
                            return None, f"Tipo de archivo no permitido ('{orig_name}'). Extensiones autorizadas: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

                        file_bytes = file_obj.read()
                        file_size = len(file_bytes)
                        if file_size > MAX_CONTENT_LENGTH:
                            conn.rollback()
                            return None, f"El archivo '{orig_name}' excede el límite permitido de 10 MB ({format_file_size(file_size)})."

                        if file_size > 0:
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_name = f"tk_{ticket_id}_{ts}_{secure_filename(orig_name)}"
                            dest_path = UPLOAD_FOLDER / safe_name
                            with open(dest_path, "wb") as f_out:
                                f_out.write(file_bytes)

                            cursor.execute("""
                                INSERT INTO ticket_adjuntos (ticket_id, usuario_id, nombre_archivo, nombre_original, tamano_bytes, tamano_formateado, mime_type)
                                VALUES (?, ?, ?, ?, ?, ?, ?);
                            """, (
                                ticket_id,
                                solicitante_id,
                                safe_name,
                                orig_name,
                                file_size,
                                format_file_size(file_size),
                                getattr(file_obj, "content_type", "application/octet-stream")
                            ))
                            adjuntos_guardados += 1

            comentario_creacion = f"Ticket registrado en el sistema. Equipo vinculado: {eq_row['codigo']} - {eq_row['nombre']}."
            if adjuntos_guardados > 0:
                comentario_creacion += f" Se adjuntó {adjuntos_guardados} archivo(s) de evidencia técnica."

            cursor.execute("""
                INSERT INTO ticket_historial (ticket_id, usuario_id, accion, comentario, estado_nuevo)
                VALUES (?, ?, 'Registro Inicial', ?, 'Abierto');
            """, (ticket_id, solicitante_id, comentario_creacion))

            conn.commit()
            new_ticket = TicketModel.get_by_id(ticket_id)
            return new_ticket, None
        except Exception as e:
            conn.rollback()
            return None, f"Error al registrar solicitud de ticket: {str(e)}"
        finally:
            conn.close()

    # =========================================================================
    # HU-07: CLASIFICAR Y ASIGNAR / REASIGNAR TICKET
    # =========================================================================

    @staticmethod
    def reassign_responsable(
        ticket_id: int,
        new_responsable_id: int | None,
        admin_user: dict,
        motivo: str = None,
        nueva_categoria: str = None,
        nueva_prioridad: str = None
    ) -> tuple[bool, str | None]:
        """
        Clasifica y asigna o reasigna un ticket a un técnico activo (HU-07).
        Criterios:
        - Persona autorizada: Exclusivo para rol 'Admin'.
        - Responsable activo: El técnico debe existir, tener rol 'Responsable' y estado 'Activo'.
        - Motivo obligatorio al reasignar: Si ya contaba con responsable previo, el motivo es obligatorio.
        - Conservar historial: Registra responsable anterior, nuevo, motivo inmutable y fecha.
        - Clasificar: Permite actualizar categoría y prioridad simultáneamente.
        """
        if admin_user.get("rol") != "Admin":
            return False, "Operación indebida: solo los Administradores tienen autorización para clasificar y asignar responsables técnicos."

        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            prev_resp_id = ticket.get("responsable_id")
            prev_resp_nombre = ticket.get("responsable_nombre") or "Sin asignar"
            new_resp_nombre = "Sin asignar"

            # 1. Validar nuevo responsable (si se está asignando uno)
            if new_responsable_id is not None:
                resp_user = conn.execute(
                    "SELECT id, nombre_completo, rol, estado FROM usuarios WHERE id = ?;",
                    (new_responsable_id,)
                ).fetchone()

                if not resp_user:
                    return False, "El técnico seleccionado no existe en el sistema."
                if resp_user["rol"] != "Responsable":
                    return False, f"El usuario seleccionado no cuenta con el rol de Responsable Técnico (Rol: {resp_user['rol']})."
                if resp_user["estado"] != "Activo":
                    return False, f"El técnico '{resp_user['nombre_completo']}' se encuentra INACTIVO y no puede recibir asignaciones."
                
                new_resp_nombre = resp_user["nombre_completo"]

            # 2. Validar motivo obligatorio al reasignar (HU-07)
            clean_motivo = (motivo or "").strip()
            es_reasignacion = (prev_resp_id is not None and prev_resp_id != new_responsable_id)
            
            if es_reasignacion and not clean_motivo:
                return False, "El motivo de la reasignación es obligatorio para garantizar la trazabilidad técnica."

            if not clean_motivo:
                clean_motivo = "Asignación técnica inicial de responsable."

            # 3. Clasificación opcional de categoría y prioridad
            cat_final = (nueva_categoria or "").strip() or ticket["categoria"]
            prio_final = (nueva_prioridad or "").strip() or ticket["prioridad"]
            if prio_final not in ('Baja', 'Media', 'Alta', 'Urgente'):
                prio_final = ticket["prioridad"]

            # 4. Actualizar tabla tickets
            cursor.execute("""
                UPDATE tickets 
                SET responsable_id = ?, categoria = ?, prioridad = ?, 
                    motivo_reasignacion = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?;
            """, (new_responsable_id, cat_final, prio_final, clean_motivo, ticket_id))

            # 5. Registrar en historial de auditoría inmutable (HU-07)
            accion_txt = "Reasignación de Responsable" if es_reasignacion else "Asignación Técnica Inicial"
            detalle_txt = f"{prev_resp_nombre} -> {new_resp_nombre}. Motivo: {clean_motivo}"
            if cat_final != ticket["categoria"] or prio_final != ticket["prioridad"]:
                detalle_txt += f" | Clasificación: Cat={cat_final}, Prio={prio_final}"

            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario, 
                    responsable_anterior_id, responsable_nuevo_id, motivo_detalle
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                admin_user["id"],
                accion_txt,
                detalle_txt,
                prev_resp_id,
                new_responsable_id,
                clean_motivo
            ))

            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f"Error al reasignar responsable: {str(e)}"
        finally:
            conn.close()

    # =========================================================================
    # HU-08: TRANSICIONES VÁLIDAS, ESPERAS, EXCEPCIONES Y TIEMPOS
    # =========================================================================

    @staticmethod
    def update_status(
        ticket_id: int,
        new_status: str,
        user: dict,
        comentario: str = None,
        ticket_relacionado_id: int = None
    ) -> tuple[bool, str | None]:
        """
        Representa avance y esperas mediante transiciones válidas (HU-08).
        Criterios:
        - Flujo válido: Registro -> Asignación/Atención -> Espera -> Resolución -> Cierre.
        - Rechazar transición inválida sin cambio de estado.
        - Motivo obligatorio en esperas (En Espera), cancelaciones (Cancelado) y duplicados (Duplicado).
        - Duplicado relacionado: folio/ticket relacionado obligatorio.
        - Distinguir y calcular tiempos: tiempo total, tiempo en espera y tiempo neto.
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return False, "Ticket no encontrado."

        old_status = ticket["estado"]
        clean_comentario = (comentario or "").strip()

        # 1. Validar permisos de actor según el rol
        if not TicketModel.user_can_modify(user, ticket):
            return False, "Operación indebida: no cuentas con permisos para cambiar el estado de este ticket."

        # Restricciones específicas por rol para el flujo (HU-08)
        if user["rol"] == "Usuario":
            # El solicitante solo puede Cerrar un ticket Resuelto o Cancelar un ticket Abierto propio
            if old_status == "Resuelto" and new_status == "Cerrado":
                pass
            elif old_status == "Abierto" and new_status == "Cancelado":
                pass
            else:
                return False, f"El rol Usuario solo puede Dar Conformidad de Cierre a tickets resueltos o Cancelar solicitudes abiertas propias."

        # 2. Validar que la transición pertenezca a la Máquina de Estados Finita
        allowed = TicketModel.VALID_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            # Caso especial: Administrador puede reabrir un ticket cerrado o reactivar un ticket
            if user["rol"] == "Admin" and old_status in ("Cerrado", "Cancelado", "Duplicado") and new_status in ("Abierto", "En Proceso"):
                pass
            else:
                return False, f"Transición de estado inválida: no se permite cambiar de '{old_status}' a '{new_status}' (Flujo permitido desde {old_status}: {', '.join(allowed) if allowed else 'Ninguno - Estado terminal'})."

        # 3. Validar motivos obligatorios en esperas y excepciones (HU-08)
        if new_status == "En Espera" and not clean_comentario:
            return False, "Debe especificar el motivo obligatorio de la espera (ej: espera de refacciones, proveedor externo, ventana de paro)."

        if new_status == "Cancelado" and not clean_comentario:
            return False, "El motivo de cancelación es obligatorio para justificar el cierre prematuro de la solicitud."

        if new_status == "Duplicado":
            if not clean_comentario:
                return False, "El motivo de duplicado es obligatorio."
            if not ticket_relacionado_id or ticket_relacionado_id == ticket_id:
                return False, "Debe seleccionar un ticket original relacionado válido que justifique la duplicidad."
            
            # Verificar que el ticket relacionado exista
            orig_ticket = TicketModel.get_by_id(ticket_relacionado_id)
            if not orig_ticket:
                return False, f"El ticket relacionado #{ticket_relacionado_id} no existe en el sistema."

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            now_dt = datetime.datetime.now()
            fmt = "%Y-%m-%d %H:%M:%S"

            # 4. Cálculo y control de tiempos (HU-08)
            fecha_inicio = ticket.get("fecha_inicio_atencion")
            fecha_res = ticket.get("fecha_resolucion")
            fecha_cie = ticket.get("fecha_cierre")
            tiempo_esp_min = ticket.get("tiempo_espera_minutos") or 0
            ult_esp_str = ticket.get("ultima_fecha_espera")
            motivo_esp = ticket.get("motivo_espera")
            motivo_canc = ticket.get("motivo_cancelacion")
            rel_id = ticket.get("ticket_relacionado_id")

            if new_status == "En Proceso":
                if not fecha_inicio:
                    fecha_inicio = now_str
                # Si venía de 'En Espera', sumar los minutos acumulados de esta pausa
                if old_status == "En Espera" and ult_esp_str:
                    try:
                        esp_dt = datetime.datetime.strptime(str(ult_esp_str)[:19], fmt)
                        delta_m = max(1, int((now_dt - esp_dt).total_seconds() / 60))
                        tiempo_esp_min += delta_m
                    except Exception:
                        pass
                ult_esp_str = None

            elif new_status == "En Espera":
                ult_esp_str = now_str
                motivo_esp = clean_comentario

            elif new_status == "Resuelto":
                fecha_res = now_str

            elif new_status == "Cerrado":
                fecha_cie = now_str

            elif new_status == "Cancelado":
                motivo_canc = clean_comentario
                fecha_cie = now_str

            elif new_status == "Duplicado":
                rel_id = ticket_relacionado_id
                motivo_canc = f"Duplicado del ticket #{orig_ticket['codigo']}. Motivo: {clean_comentario}"
                fecha_cie = now_str

            # Actualizar tabla tickets
            cursor.execute("""
                UPDATE tickets 
                SET estado = ?, motivo_espera = ?, motivo_cancelacion = ?,
                    ticket_relacionado_id = ?, fecha_inicio_atencion = ?,
                    fecha_resolucion = ?, fecha_cierre = ?, tiempo_espera_minutos = ?,
                    ultima_fecha_espera = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (
                new_status, motivo_esp, motivo_canc, rel_id,
                fecha_inicio, fecha_res, fecha_cie, tiempo_esp_min,
                ult_esp_str, ticket_id
            ))

            # 5. Registrar en historial de auditoría inmutable (HU-08)
            accion_txt = f"Cambio de estado: {old_status} -> {new_status}"
            comentario_historial = clean_comentario or f"Transición de estado a [{new_status}]."
            if new_status == "Duplicado":
                comentario_historial = f"Marcado como duplicado de {orig_ticket['codigo']}. {clean_comentario}"

            cursor.execute("""
                INSERT INTO ticket_historial (
                    ticket_id, usuario_id, accion, comentario, 
                    estado_anterior, estado_nuevo, motivo_detalle
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                user["id"],
                accion_txt,
                comentario_historial,
                old_status,
                new_status,
                clean_comentario
            ))

            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f"Error al actualizar estado: {str(e)}"
        finally:
            conn.close()

    # =========================================================================
    # HU-09: COMENTARIOS Y EVIDENCIAS CRONOLÓGICAS DURANTE LA ATENCIÓN
    # =========================================================================

    @staticmethod
    def add_comment(
        ticket_id: int,
        user: dict,
        comentario: str,
        archivo=None
    ) -> tuple[dict | None, str | None]:
        """
        Registra comentarios y evidencias cronológicos durante la atención (HU-09).
        Criterios:
        - Participante autorizado: Solo Admin, Responsable asignado o Solicitante.
        - Inmutabilidad: Autor (usuario_id) y fecha (created_at) son inalterables.
        - Orden cronológico garantizado en bitácora.
        - Adjuntos dentro del límite <= 10 MB vinculados a la nota.
        """
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket no encontrado."

        # Control estricto de participante autorizado (HU-09)
        if not TicketModel.user_can_view(user, ticket):
            return None, "Operación denegada (403): no cuentas con autorización para comentar en este ticket."

        clean_comentario = (comentario or "").strip()
        tiene_archivo = bool(archivo and getattr(archivo, "filename", None))

        if not clean_comentario and not tiene_archivo:
            return None, "El comentario no puede estar vacío."

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            adjunto_info = None

            # Procesar archivo adjunto si viene con el comentario (HU-09)
            if tiene_archivo:
                orig_name = os.path.basename(archivo.filename)
                if not is_allowed_file(orig_name):
                    return None, f"Tipo de archivo no permitido ('{orig_name}'). Extensiones autorizadas: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

                file_bytes = archivo.read()
                file_size = len(file_bytes)
                if file_size > MAX_CONTENT_LENGTH:
                    return None, f"El archivo excede el límite permitido de 10 MB ({format_file_size(file_size)})."

                if file_size > 0:
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = f"tk_{ticket_id}_com_{ts}_{secure_filename(orig_name)}"
                    dest_path = UPLOAD_FOLDER / safe_name
                    with open(dest_path, "wb") as f_out:
                        f_out.write(file_bytes)

                    cursor.execute("""
                        INSERT INTO ticket_adjuntos (ticket_id, usuario_id, nombre_archivo, nombre_original, tamano_bytes, tamano_formateado, mime_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (
                        ticket_id,
                        user["id"],
                        safe_name,
                        orig_name,
                        file_size,
                        format_file_size(file_size),
                        getattr(archivo, "content_type", "application/octet-stream")
                    ))
                    adj_id = cursor.lastrowid
                    adjunto_info = f" [Evidencia adjunta: {orig_name} ({format_file_size(file_size)})]"

            comentario_final = clean_comentario or "Evidencia técnica adjuntada durante la atención."
            if adjunto_info:
                comentario_final += adjunto_info

            # Registrar en historial con autor inmutable y fecha inmutable (HU-09)
            cursor.execute("""
                INSERT INTO ticket_historial (ticket_id, usuario_id, accion, comentario, motivo_detalle)
                VALUES (?, ?, 'Comentario / Nota de Seguimiento', ?, ?);
            """, (ticket_id, user["id"], comentario_final, clean_comentario))

            cursor.execute("UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (ticket_id,))
            conn.commit()

            hist_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM ticket_historial WHERE id = ?;", (hist_id,)).fetchone()
            return dict(row), None
        except Exception as e:
            conn.rollback()
            return None, f"Error al registrar comentario: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def add_attachment_to_ticket(ticket_id: int, user: dict, file_obj) -> tuple[dict | None, str | None]:
        """Adjunta una evidencia adicional respetando permisos y límite <= 10 MB (HU-05 y HU-09)."""
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            return None, "Ticket no encontrado."

        if not TicketModel.user_can_view(user, ticket):
            return None, "Acceso denegado (403): no tienes autorización para adjuntar archivos en este ticket."

        if not file_obj or not getattr(file_obj, "filename", None):
            return None, "No se seleccionó ningún archivo."

        orig_name = os.path.basename(file_obj.filename)
        if not is_allowed_file(orig_name):
            return None, f"Tipo de archivo no permitido ('{orig_name}')."

        file_bytes = file_obj.read()
        file_size = len(file_bytes)
        if file_size > MAX_CONTENT_LENGTH:
            return None, f"El archivo excede el límite permitido de 10 MB ({format_file_size(file_size)})."

        if file_size == 0:
            return None, "El archivo seleccionado está vacío."

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"tk_{ticket_id}_{ts}_{secure_filename(orig_name)}"
        dest_path = UPLOAD_FOLDER / safe_name
        with open(dest_path, "wb") as f_out:
            f_out.write(file_bytes)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ticket_adjuntos (ticket_id, usuario_id, nombre_archivo, nombre_original, tamano_bytes, tamano_formateado, mime_type)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                ticket_id,
                user["id"],
                safe_name,
                orig_name,
                file_size,
                format_file_size(file_size),
                getattr(file_obj, "content_type", "application/octet-stream")
            ))
            adj_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO ticket_historial (ticket_id, usuario_id, accion, comentario, motivo_detalle)
                VALUES (?, ?, 'Evidencia Adjuntada', ?, ?);
            """, (
                ticket_id,
                user["id"],
                f"Evidencia técnica adjuntada: {orig_name} ({format_file_size(file_size)}).",
                orig_name
            ))

            conn.commit()
            adj = conn.execute("SELECT * FROM ticket_adjuntos WHERE id = ?;", (adj_id,)).fetchone()
            return dict(adj), None
        except Exception as e:
            conn.rollback()
            return None, f"Error al guardar archivo adjunto: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def get_attachments(ticket_id: int):
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT ta.*, u.nombre_completo AS usuario_nombre, u.rol AS usuario_rol
            FROM ticket_adjuntos ta
            LEFT JOIN usuarios u ON ta.usuario_id = u.id
            WHERE ta.ticket_id = ? 
            ORDER BY ta.id ASC;
        """, (ticket_id,)).fetchall()
        conn.close()
        return [dict(a) for a in rows]

    @staticmethod
    def get_attachment(attachment_id: int):
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM ticket_adjuntos WHERE id = ?;", (attachment_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_history(ticket_id: int):
        """Retorna la bitácora cronológica inmutable con datos de autores (HU-09)."""
        conn = get_db_connection()
        query = """
            SELECT h.*, 
                   u.nombre_completo AS usuario_nombre, u.rol AS usuario_rol,
                   ra.nombre_completo AS resp_anterior_nombre,
                   rn.nombre_completo AS resp_nuevo_nombre
            FROM ticket_historial h
            JOIN usuarios u ON h.usuario_id = u.id
            LEFT JOIN usuarios ra ON h.responsable_anterior_id = ra.id
            LEFT JOIN usuarios rn ON h.responsable_nuevo_id = rn.id
            WHERE h.ticket_id = ?
            ORDER BY h.id ASC;
        """
        rows = conn.execute(query, (ticket_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_stats_for_user(user: dict):
        tickets = TicketModel.get_tickets_for_user(user)
        total = len(tickets)
        abiertos = sum(1 for t in tickets if t["estado"] == "Abierto")
        en_proceso = sum(1 for t in tickets if t["estado"] == "En Proceso")
        en_espera = sum(1 for t in tickets if t["estado"] == "En Espera")
        resueltos = sum(1 for t in tickets if t["estado"] == "Resuelto")
        cerrados = sum(1 for t in tickets if t["estado"] == "Cerrado")
        cancelados = sum(1 for t in tickets if t["estado"] in ("Cancelado", "Duplicado"))
        urgentes = sum(1 for t in tickets if t["prioridad"] == "Urgente" and t["estado"] not in ("Resuelto", "Cerrado", "Cancelado", "Duplicado"))

        return {
            "total": total,
            "abiertos": abiertos,
            "en_proceso": en_proceso,
            "en_espera": en_espera,
            "resueltos": resueltos,
            "cerrados": cerrados,
            "cancelados": cancelados,
            "urgentes": urgentes
        }
