import os
import sys
import datetime
import webbrowser
import threading
from pathlib import Path

# Asegurar importaciones relativas
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Detección y adición automática de paquetes instalados (Flask, Werkzeug, Jinja2, etc.)
site_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for sp in site_candidates:
    if sp.is_dir() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))

try:
    from flask import Flask, render_template, request, redirect, url_for, session, abort, send_from_directory, jsonify, Response
    from werkzeug.exceptions import RequestEntityTooLarge
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    unity_python = r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\python.exe"
    if __name__ == "__main__" and os.path.isfile(unity_python) and sys.executable.lower() != unity_python.lower():
        import subprocess
        sys.exit(subprocess.call([unity_python] + sys.argv))
    raise

from config import (
    SECRET_KEY, SERVER_HOST, SERVER_PORT, COMPANY_NAME, SYSTEM_NAME, 
    TIMEZONE_LABEL, UPLOAD_FOLDER, MAX_CONTENT_LENGTH
)
from database.db import init_db
from models.user import UserModel
from models.ticket import TicketModel, ReportsModel
from models.equipment import EquipmentModel, AreaModel, CatalogModel
from auth.security import verify_password, revoke_all_user_sessions

# Inicialización de la aplicación Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH  # Límite estricto 10 MB (HU-05)

# Configuración del cargador de plantillas dividido por Sprints (Sprint 1 a 4)
import jinja2
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(str(BASE_DIR / "templates" / "sprint_4")),
    jinja2.FileSystemLoader(str(BASE_DIR / "templates" / "sprint_3")),
    jinja2.FileSystemLoader(str(BASE_DIR / "templates" / "sprint_2")),
    jinja2.FileSystemLoader(str(BASE_DIR / "templates" / "sprint_1")),
    jinja2.FileSystemLoader(str(BASE_DIR / "templates")),
])
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}

# Inyección de variables corporativas globales en las plantillas Jinja2
@app.context_processor
def inject_globals():
    return {
        "COMPANY_NAME": COMPANY_NAME,
        "SYSTEM_NAME": SYSTEM_NAME,
        "TIMEZONE_LABEL": TIMEZONE_LABEL
    }

# Evitar caché del navegador para asegurar renderizado en tiempo real de plantillas y alertas
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def get_logged_user():
    """Retorna el usuario actual autenticado verificando que siga activo (HU-01 y HU-03)."""
    uid = session.get("user_id")
    if not uid:
        return None
    user = UserModel.get_by_id(uid)
    if not user or user.get("estado") != "Activo":
        session.clear()
        return None
    return user

# =========================================================================
# HISTORIA DE USUARIO 1: AUTENTICACIÓN Y SESIÓN SEGURA
# =========================================================================

@app.route("/")
def index():
    user = get_logged_user()
    if user:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    user = get_logged_user()
    if user:
        return redirect(url_for("dashboard"))

    notice = None
    if request.args.get("notice") == "logged_out":
        notice = "Tu sesión ha finalizado correctamente. Por seguridad, debes volver a autenticarte para acceder a páginas protegidas."
    elif request.args.get("notice") == "registered":
        notice = "Cuenta de Usuario creada con éxito. Ya puedes iniciar sesión con tus credenciales."
    elif request.args.get("notice") == "pwd_reset":
        notice = "Tu contraseña ha sido restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."

    if request.method == "POST":
        identificador = (request.form.get("identificador") or "").strip()
        password = request.form.get("password") or ""

        target_user = UserModel.get_by_identifier(identificador)
        is_valid = False
        if target_user:
            pwd_matches = verify_password(password, target_user["password_hash"], target_user["salt"])
            is_active = (target_user["estado"] == "Activo")
            if pwd_matches and is_active:
                is_valid = True

        if not is_valid:
            # Mensaje uniforme del Mockup 2: credenciales inválidas no revelan cuál dato falló (HU-01)
            error_msg = "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa. Contacte al administrador."
            user_not_found = (target_user is None and bool(identificador))
            default_nombre = identificador.split("@")[0].replace(".", " ").replace("_", " ").title() if identificador else ""
            return render_template(
                "login.html",
                error=error_msg,
                notice=None,
                identifier_val=identificador,
                password_val=password,
                user_not_found=user_not_found,
                default_nombre=default_nombre,
                has_error=True
            ), 401

        # Inicio de sesión exitoso
        session["user_id"] = target_user["id"]
        session["role"] = target_user["rol"]
        return redirect(url_for("dashboard"))

    return render_template("login.html", error=None, notice=notice, identifier_val="", user_not_found=False)

@app.route("/register", methods=["GET", "POST"])
def register():
    user = get_logged_user()
    if user:
        return redirect(url_for("dashboard"))

    error = None
    identificador = (request.form.get("identificador") or request.args.get("identificador") or "").strip()
    password = request.form.get("password") or ""
    nombre_completo = (request.form.get("nombre_completo") or "").strip()

    if request.method == "POST":
        confirm_pwd = request.form.get("confirm_password")
        if confirm_pwd is not None and confirm_pwd != password:
            error = "Las contraseñas ingresadas no coinciden."
            return render_template("register.html", error=error, identificador=identificador, nombre_completo=nombre_completo), 400

        new_user, err = UserModel.register_user(
            identificador=identificador,
            password=password,
            nombre_completo=nombre_completo
        )
        if err:
            return render_template("register.html", error=err, identificador=identificador, nombre_completo=nombre_completo), 400

        # Iniciar sesión automáticamente con rol Usuario y redirigir al Dashboard
        session["user_id"] = new_user["id"]
        session["role"] = new_user["rol"]
        return redirect(url_for("dashboard"))

    return render_template("register.html", error=None, identificador=identificador, nombre_completo=nombre_completo)

@app.route("/recuperar-password", methods=["GET", "POST"])
def recuperar_password():
    user = get_logged_user()
    if user:
        return redirect(url_for("dashboard"))

    error = None
    identificador = (request.form.get("identificador") or request.args.get("identificador") or "").strip()

    if request.method == "POST":
        nueva_contrasena = request.form.get("nueva_contrasena") or ""
        confirm_pwd = request.form.get("confirm_password") or ""

        # Validar que el correo contenga sí o sí @
        if not identificador or "@" not in identificador:
            error = "El correo electrónico es obligatorio y debe contener el símbolo '@' (ejemplo: usuario@bajio.mx)."
            return render_template("recuperar_password.html", error=error, identificador=identificador), 400

        if nueva_contrasena != confirm_pwd:
            error = "Las contraseñas no coinciden. Verifícalas e inténtalo nuevamente."
            return render_template("recuperar_password.html", error=error, identificador=identificador), 400

        ok, err = UserModel.reset_password(identificador, nueva_contrasena)
        if not ok:
            return render_template("recuperar_password.html", error=err, identificador=identificador), 400

        return redirect(url_for("login", notice="pwd_reset"))

    return render_template("recuperar_password.html", error=None, identificador=identificador)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login", notice="logged_out"))

# =========================================================================
# HISTORIA DE USUARIO 2: CONTROL DE ACCESO POR ROL Y PARTICIPACIÓN
# =========================================================================

@app.route("/dashboard")
def dashboard():
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    stats = TicketModel.get_stats_for_user(user)
    recent_tickets = TicketModel.get_tickets_for_user(user)[:6]
    return render_template("dashboard.html", user=user, stats=stats, recent_tickets=recent_tickets)

# =========================================================================
# HISTORIA DE USUARIO 4: CATÁLOGOS Y EQUIPOS
# =========================================================================

@app.route("/equipos")
def equipos_list():
    """Listado y consulta de equipos (HU-04). Visible para participantes y administrable por Admin."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    search = request.args.get("q")
    area_id = request.args.get("area_id")
    estado = request.args.get("estado")

    # Si es usuario no-admin y no filtra estado, puede ver activos o todos
    equipos = EquipmentModel.get_all(search=search, area_id=area_id, estado=estado)
    areas = AreaModel.get_all()

    success_msg = None
    msg_param = request.args.get("msg")
    if msg_param == "created":
        success_msg = "Equipo registrado exitosamente en el catálogo."
    elif msg_param == "updated":
        success_msg = "Datos del equipo y periodicidad preventiva actualizados correctamente."
    elif msg_param == "status_changed":
        success_msg = "Estado del equipo modificado. Se conservan todas las referencias históricas."

    return render_template(
        "equipos/list.html",
        user=user,
        equipos=equipos,
        areas=areas,
        search=search or "",
        area_filter=area_id or "",
        estado_filter=estado or "",
        success_msg=success_msg,
        error_msg=request.args.get("err")
    )

@app.route("/equipos/nuevo", methods=["GET", "POST"])
def equipo_create():
    """Alta de nuevo equipo en el catálogo con periodicidad preventiva (Admin - HU-04)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))
    if user["rol"] != "Admin":
        abort(403)

    areas = AreaModel.get_all()

    if request.method == "POST":
        codigo = request.form.get("codigo") or ""
        nombre = request.form.get("nombre") or ""
        marca = request.form.get("marca") or ""
        modelo = request.form.get("modelo") or ""
        numero_serie = request.form.get("numero_serie") or ""
        area_id = request.form.get("area_id") or ""
        ubicacion = request.form.get("ubicacion_especifica") or ""
        periodicidad = request.form.get("periodicidad_dias") or 90
        fecha_ultimo = request.form.get("fecha_ultimo_mantenimiento") or ""
        estado = request.form.get("estado") or "Activo"

        eq, err = EquipmentModel.create_equipment(
            codigo=codigo,
            nombre=nombre,
            marca=marca,
            modelo=modelo,
            numero_serie=numero_serie,
            area_id=int(area_id) if area_id and str(area_id).isdigit() else None,
            ubicacion_especifica=ubicacion,
            periodicidad_dias=periodicidad,
            fecha_ultimo_mantenimiento=fecha_ultimo,
            estado=estado
        )
        if err:
            return render_template(
                "equipos/form.html",
                user=user,
                areas=areas,
                form_title="Registrar Nuevo Equipo Industrial",
                form_action="/equipos/nuevo",
                eq=None,
                error_msg=err,
                form_codigo=codigo,
                form_nombre=nombre,
                form_marca=marca,
                form_modelo=modelo,
                form_serie=numero_serie,
                form_area_id=area_id,
                form_ubicacion=ubicacion,
                form_periodicidad=periodicidad,
                form_fecha_ultimo=fecha_ultimo,
                form_estado=estado
            ), 400

        return redirect(url_for("equipos_list", msg="created"))

    return render_template(
        "equipos/form.html",
        user=user,
        areas=areas,
        form_title="Registrar Nuevo Equipo Industrial",
        form_action="/equipos/nuevo",
        eq=None,
        error_msg=None
    )

@app.route("/equipos/<int:id>/editar", methods=["GET", "POST"])
def equipo_edit(id):
    """Edición de equipo y ajuste de periodicidad preventiva (Admin - HU-04)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))
    if user["rol"] != "Admin":
        abort(403)

    eq = EquipmentModel.get_by_id(id)
    if not eq:
        abort(404)

    areas = AreaModel.get_all()

    if request.method == "POST":
        codigo = request.form.get("codigo") or ""
        nombre = request.form.get("nombre") or ""
        marca = request.form.get("marca") or ""
        modelo = request.form.get("modelo") or ""
        numero_serie = request.form.get("numero_serie") or ""
        area_id = request.form.get("area_id") or ""
        ubicacion = request.form.get("ubicacion_especifica") or ""
        periodicidad = request.form.get("periodicidad_dias") or 90
        fecha_ultimo = request.form.get("fecha_ultimo_mantenimiento") or ""
        estado = request.form.get("estado") or "Activo"

        _, err = EquipmentModel.update_equipment(
            equipment_id=id,
            codigo=codigo,
            nombre=nombre,
            marca=marca,
            modelo=modelo,
            numero_serie=numero_serie,
            area_id=int(area_id) if area_id and str(area_id).isdigit() else eq["area_id"],
            ubicacion_especifica=ubicacion,
            periodicidad_dias=periodicidad,
            fecha_ultimo_mantenimiento=fecha_ultimo,
            estado=estado
        )
        if err:
            return render_template(
                "equipos/form.html",
                user=user,
                areas=areas,
                form_title="Editar Equipo Industrial",
                form_action=f"/equipos/{id}/editar",
                eq=eq,
                error_msg=err
            ), 400

        return redirect(url_for("equipos_list", msg="updated"))

    return render_template(
        "equipos/form.html",
        user=user,
        areas=areas,
        form_title="Editar Equipo Industrial",
        form_action=f"/equipos/{id}/editar",
        eq=eq,
        error_msg=None
    )

@app.route("/equipos/<int:id>/toggle-status", methods=["POST"])
def equipo_toggle_status(id):
    """Activar/desactivar equipo conservando referencias históricas (Admin - HU-04)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))
    if user["rol"] != "Admin":
        abort(403)

    _, err = EquipmentModel.toggle_status(id)
    if err:
        return redirect(url_for("equipos_list", err=err))
    return redirect(url_for("equipos_list", msg="status_changed"))

@app.route("/admin/areas", methods=["GET", "POST"])
@app.route("/areas", methods=["GET"])
def admin_areas():
    """Mantenimiento y consulta de catálogo de áreas industriales (HU-04)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    if request.method == "POST":
        if user["rol"] != "Admin":
            abort(403)
        codigo = request.form.get("codigo") or ""
        nombre = request.form.get("nombre") or ""
        desc = request.form.get("descripcion") or ""
        estado = request.form.get("estado") or "Activo"

        _, err = AreaModel.create_area(codigo, nombre, desc, estado)
        if err:
            areas = AreaModel.get_all()
            return render_template("admin/areas.html", user=user, areas=areas, error_msg=err), 400
        return redirect(url_for("admin_areas", msg="area_created"))

    areas = AreaModel.get_all()
    success_msg = None
    if request.args.get("msg") == "area_created":
        success_msg = "Área registrada exitosamente."
    elif request.args.get("msg") == "status_changed":
        success_msg = "Estado del área actualizado correctamente."

    return render_template("admin/areas.html", user=user, areas=areas, success_msg=success_msg, error_msg=request.args.get("err"))

@app.route("/admin/areas/<int:id>/toggle-status", methods=["POST"])
def admin_area_toggle(id):
    user = get_logged_user()
    if not user or user["rol"] != "Admin":
        abort(403)

    _, err = AreaModel.toggle_status(id)
    if err:
        return redirect(url_for("admin_areas", err=err))
    return redirect(url_for("admin_areas", msg="status_changed"))

# =========================================================================
# HISTORIA DE USUARIO 5 Y 6: SOLICITUD DE TICKETS Y CONSULTA AVANZADA
# =========================================================================

@app.route("/tickets")
def tickets():
    """
    Listado y filtrado de tickets visibles para el participante (HU-06).
    Criterios:
    - Búsqueda por folio o palabra clave.
    - Filtros avanzados: equipo, solicitante, responsable, área, prioridad y estado.
    - Manejo coherente de estado 'sin resultados'.
    """
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    search = request.args.get("q")
    folio = request.args.get("folio")
    equipo = request.args.get("equipo")
    solicitante = request.args.get("solicitante")
    responsable = request.args.get("responsable")
    area = request.args.get("area")
    prioridad = request.args.get("prioridad")
    estado = request.args.get("estado")
    categoria = request.args.get("categoria")

    # Si se pasa folio por parámetro separado o dentro de q
    ticket_list = TicketModel.get_tickets_for_user(
        user=user,
        search=search,
        folio=folio,
        equipo_id=equipo,
        solicitante_id=solicitante,
        responsable_id=responsable,
        area_id=area,
        prioridad=prioridad,
        estado=estado,
        categoria=categoria
    )

    # Catálogos para los dropdowns de filtrado (HU-06)
    filter_equipos = EquipmentModel.get_all()
    filter_areas = AreaModel.get_all()
    filter_solicitantes = UserModel.get_all() if user["rol"] in ("Admin", "Responsable") else []
    filter_responsables = UserModel.get_all(role="Responsable") if user["rol"] == "Admin" else []

    return render_template(
        "tickets/list.html",
        user=user,
        tickets=ticket_list,
        search=search or "",
        equipo_filter=equipo or "",
        solicitante_filter=solicitante or "",
        responsable_filter=responsable or "",
        area_filter=area or "",
        prioridad_filter=prioridad or "",
        estado_filter=estado or "",
        categoria_filter=categoria or "",
        filter_equipos=filter_equipos,
        filter_areas=filter_areas,
        filter_solicitantes=filter_solicitantes,
        filter_responsables=filter_responsables
    )

@app.route("/tickets/nuevo", methods=["GET", "POST"])
def ticket_create():
    """
    Registrar solicitud de ticket relacionada con equipo activo (HU-05).
    Criterios:
    - Equipo activo: se valida existencia y estado 'Activo'.
    - Obligatorios validados: título, situación, detector, equipo, categoría, prioridad.
    - Folio único consecutivo generado en el servidor.
    - Evidencia adjunta con límite estricto <= 10 MB.
    """
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    equipos_activos = EquipmentModel.get_active()
    categorias = CatalogModel.get_categories()
    responsables = UserModel.get_all(role="Responsable", status="Activo") if user["rol"] == "Admin" else []

    if request.method == "POST":
        titulo = request.form.get("titulo") or ""
        situacion = request.form.get("situacion_problema") or ""
        detector = request.form.get("detector_nombre") or ""
        equipo_id_raw = request.form.get("equipo_id")
        categoria = request.form.get("categoria") or "Automatización Industrial"
        prioridad = request.form.get("prioridad") or "Media"
        ubicacion = request.form.get("ubicacion_equipo") or ""

        resp_id = None
        if user["rol"] == "Admin":
            raw_resp = request.form.get("responsable_id")
            if raw_resp and raw_resp.isdigit():
                resp_id = int(raw_resp)

        equipo_id = int(equipo_id_raw) if equipo_id_raw and str(equipo_id_raw).isdigit() else None

        # Procesar archivos adjuntos (HU-05: <= 10 MB)
        archivos = []
        if "evidencia" in request.files:
            file_obj = request.files.get("evidencia")
            if file_obj and file_obj.filename:
                archivos.append(file_obj)

        new_t, err = TicketModel.create_ticket(
            titulo=titulo,
            situacion_problema=situacion,
            detector_nombre=detector,
            equipo_id=equipo_id,
            categoria=categoria,
            prioridad=prioridad,
            solicitante_id=user["id"],
            responsable_id=resp_id,
            ubicacion_equipo=ubicacion,
            archivos=archivos
        )
        if err:
            return render_template(
                "tickets/create.html",
                user=user,
                equipos_activos=equipos_activos,
                categorias=categorias,
                responsables=responsables,
                error_msg=err,
                form_titulo=titulo,
                form_situacion=situacion,
                form_detector=detector,
                form_equipo_id=str(equipo_id or ""),
                form_categoria=categoria,
                form_prioridad=prioridad,
                form_ubicacion=ubicacion,
                form_responsable_id=str(resp_id or "")
            ), 400

        return redirect(url_for("ticket_detail", id=new_t["id"], msg="ticket_created"))

    return render_template(
        "tickets/create.html",
        user=user,
        equipos_activos=equipos_activos,
        categorias=categorias,
        responsables=responsables,
        error_msg=None,
        form_detector=user["nombre_completo"]
    )

@app.route("/tickets/<int:id>")
def ticket_detail(id):
    """
    Detalle coherente y protegido por rol y participación (HU-02, HU-06, HU-07, HU-08, HU-09).
    Muestra:
    - Datos del ticket, folio único, estado y prioridad.
    - Solicitante y persona que detectó la falla (detector_nombre).
    - Equipo industrial vinculado, su localización física, periodicidad y estado.
    - Métricas de tiempos (tiempo total, tiempo en espera y tiempo neto de atención).
    - Transiciones de estado permitidas según Máquina de Estados Finita.
    - Evidencias adjuntas (descarga directa) y bitácora cronológica inmutable.
    """
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    ticket = TicketModel.get_by_id(id)
    if not ticket:
        return render_template("errors/404.html", user=user, title="Ticket no encontrado", message=f"El ticket #{id} no existe en el sistema."), 404

    # Control estricto de visibilidad por rol y participación (HU-02 y HU-06)
    if not TicketModel.user_can_view(user, ticket):
        return render_template(
            "errors/403.html",
            user=user,
            title="Acceso Denegado (403)",
            message="No tienes autorización para consultar la información de este ticket. Solo el solicitante, el técnico responsable asignado o un Administrador tienen acceso a este registro.",
            back_url="/tickets"
        ), 403

    can_modify = TicketModel.user_can_modify(user, ticket)
    is_admin = (user["rol"] == "Admin")
    is_responsable = (user["rol"] == "Responsable" and ticket.get("responsable_id") == user["id"])
    responsables = UserModel.get_all(role="Responsable", status="Activo") if is_admin else []
    categorias = CatalogModel.get_categories() if is_admin else []
    history = TicketModel.get_history(id)

    # Calcular transiciones válidas según FSM y rol (HU-08)
    curr_status = ticket["estado"]
    allowed_transitions = TicketModel.VALID_TRANSITIONS.get(curr_status, [])
    if user["rol"] == "Usuario":
        allowed_transitions = [s for s in allowed_transitions if (curr_status == "Resuelto" and s == "Cerrado") or (curr_status == "Abierto" and s == "Cancelado")]
    elif user["rol"] == "Responsable":
        allowed_transitions = [s for s in allowed_transitions if s in ("En Proceso", "En Espera", "Resuelto")]

    # Tickets relacionados disponibles para marcar Duplicado
    other_tickets = [t for t in TicketModel.get_tickets_for_user(user) if t["id"] != id] if is_admin else []

    msg_param = request.args.get("msg")
    success_msg = None
    if msg_param == "ticket_created":
        success_msg = f"Solicitud registrada exitosamente con folio único {ticket['codigo']}."
    elif msg_param == "status_updated":
        success_msg = "Estado del ticket actualizado satisfactoriamente según el flujo de atención."
    elif msg_param == "reassigned":
        success_msg = "Técnico responsable asignado/reclasificado correctamente con motivo registrado en auditoría."
    elif msg_param == "comment_added":
        success_msg = "Nota de seguimiento o evidencia técnica registrada en la bitácora cronológica."
    elif msg_param == "file_uploaded":
        success_msg = "Evidencia técnica adjunta correctamente al ticket (dentro del límite de 10 MB)."
    elif msg_param == "resolved":
        success_msg = "Resolución técnica registrada exitosamente en el ticket."
    elif msg_param == "closed":
        success_msg = "Ticket cerrado formalmente. Se ha establecido el bloqueo estricto contra modificaciones ordinarias."
    elif msg_param == "recurrence_created":
        success_msg = "Atención nueva por recurrencia creada y vinculada bidireccionalmente con éxito."

    return render_template(
        "tickets/detail.html",
        user=user,
        ticket=ticket,
        can_modify=can_modify,
        is_admin=is_admin,
        is_responsable=is_responsable,
        responsables=responsables,
        categorias=categorias,
        allowed_transitions=allowed_transitions,
        other_tickets=other_tickets,
        history=history,
        success_msg=success_msg,
        error_msg=request.args.get("err")
    )

@app.route("/tickets/<int:id>/adjuntar", methods=["POST"])
def ticket_attach_file(id):
    """Adjuntar evidencia técnica adicional a un ticket existente (HU-05 y HU-09: <= 10 MB)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    file_obj = request.files.get("archivo")
    _, err = TicketModel.add_attachment_to_ticket(id, user, file_obj)
    if err:
        return redirect(url_for("ticket_detail", id=id, err=err))
    return redirect(url_for("ticket_detail", id=id, msg="file_uploaded"))

@app.route("/tickets/adjuntos/<int:attachment_id>")
def download_attachment(attachment_id):
    """Descarga segura de archivo de evidencia con verificación de acceso RBAC (HU-09)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    adj = TicketModel.get_attachment(attachment_id)
    if not adj:
        abort(404)

    ticket = TicketModel.get_by_id(adj["ticket_id"])
    if not ticket or not TicketModel.user_can_view(user, ticket):
        abort(403)

    return send_from_directory(
        UPLOAD_FOLDER,
        adj["nombre_archivo"],
        as_attachment=True,
        download_name=adj["nombre_original"]
    )

@app.route("/tickets/<int:id>/status", methods=["POST"])
def ticket_status(id):
    """Transición de estado del ticket con validación FSM y motivos obligatorios (HU-08)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    ticket = TicketModel.get_by_id(id)
    if not ticket or not TicketModel.user_can_modify(user, ticket):
        return render_template(
            "errors/403.html",
            user=user,
            title="Operación Indebida Rechazada",
            message="No tienes autorización para cambiar el estado de este ticket.",
            back_url=f"/tickets/{id}"
        ), 403

    new_status = request.form.get("estado") or ""
    comentario = request.form.get("comentario") or ""
    rel_raw = request.form.get("ticket_relacionado_id")
    rel_id = int(rel_raw) if rel_raw and rel_raw.isdigit() else None

    ok, err = TicketModel.update_status(id, new_status, user, comentario, ticket_relacionado_id=rel_id)
    if not ok:
        return redirect(url_for("ticket_detail", id=id, err=err))
    return redirect(url_for("ticket_detail", id=id, msg="status_updated"))

@app.route("/tickets/<int:id>/reassign", methods=["POST"])
def ticket_reassign_route(id):
    """Clasificar y asignar/reasignar ticket con motivo obligatorio y técnico activo (HU-07)."""
    user = get_logged_user()
    if not user or user["rol"] != "Admin":
        return render_template(
            "errors/403.html",
            user=user,
            title="Operación Indebida Rechazada",
            message="Únicamente los Administradores tienen autorización para clasificar y reasignar técnicos responsables.",
            back_url=f"/tickets/{id}"
        ), 403

    new_resp_id = request.form.get("responsable_id")
    motivo = request.form.get("motivo") or request.form.get("comentario") or ""
    categoria = request.form.get("categoria")
    prioridad = request.form.get("prioridad")
    resp_val = int(new_resp_id) if new_resp_id and new_resp_id.isdigit() else None

    ok, err = TicketModel.reassign_responsable(
        ticket_id=id,
        new_responsable_id=resp_val,
        admin_user=user,
        motivo=motivo,
        nueva_categoria=categoria,
        nueva_prioridad=prioridad
    )
    if not ok:
        return redirect(url_for("ticket_detail", id=id, err=err))
    return redirect(url_for("ticket_detail", id=id, msg="reassigned"))

@app.route("/tickets/<int:id>/comentar", methods=["POST"])
def ticket_comment_route(id):
    """Registrar comentarios y evidencias cronológicos durante la atención (HU-09)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    comentario = request.form.get("comentario") or ""
    archivo = request.files.get("archivo") if "archivo" in request.files else None

    _, err = TicketModel.add_comment(id, user, comentario, archivo=archivo)
    if err:
        return redirect(url_for("ticket_detail", id=id, err=err))
    return redirect(url_for("ticket_detail", id=id, msg="comment_added"))

# =========================================================================
# SPRINT 4: HU-10 (RESOLUCIÓN Y CIERRE), HU-11 (TRAZABILIDAD), HU-12 (REPORTES Y CSV)
# =========================================================================

@app.route("/tickets/<int:id>/resolver", methods=["POST"])
def ticket_resolve_route(id):
    """Registrar la resolución técnica implementada (HU-10)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    solucion = request.form.get("solucion_detalle") or ""
    ok, err = TicketModel.resolve_ticket(id, user, solucion)
    if not ok:
        return redirect(url_for("ticket_detail", id=id, err=err))

    # Adjuntar evidencia opcional junto con la resolución
    if "archivo" in request.files and request.files["archivo"].filename:
        TicketModel.add_attachment_to_ticket(id, user, request.files["archivo"])

    return redirect(url_for("ticket_detail", id=id, msg="resolved"))

@app.route("/tickets/<int:id>/cerrar", methods=["POST"])
def ticket_close_route(id):
    """Confirmar el cierre del ticket con o sin solución justificada (HU-10)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    tipo_cierre = request.form.get("tipo_cierre") or "Con Solución"
    detalle_o_motivo = (
        request.form.get("detalle_o_motivo") or 
        request.form.get("motivo_sin_solucion") or 
        request.form.get("solucion_detalle") or 
        request.form.get("comentario") or ""
    )

    ok, err = TicketModel.close_ticket(id, user, tipo_cierre, detalle_o_motivo)
    if not ok:
        return redirect(url_for("ticket_detail", id=id, err=err))
    return redirect(url_for("ticket_detail", id=id, msg="closed"))

@app.route("/tickets/<int:id>/recurrencia", methods=["POST"])
def ticket_recurrence_route(id):
    """Crear nueva atención relacionada cuando reaparece la falla (HU-10)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    situacion = request.form.get("situacion_falla") or request.form.get("comentario") or ""
    prioridad = request.form.get("prioridad")
    detector = request.form.get("detector_nombre")

    nuevo_ticket, err = TicketModel.create_recurrence(
        ticket_id=id,
        user=user,
        situacion_falla=situacion,
        prioridad=prioridad,
        detector_nombre=detector
    )
    if err or not nuevo_ticket:
        return redirect(url_for("ticket_detail", id=id, err=err or "Error al crear recurrencia."))

    if "archivo" in request.files and request.files["archivo"].filename:
        TicketModel.add_attachment_to_ticket(nuevo_ticket["id"], user, request.files["archivo"])

    return redirect(url_for("ticket_detail", id=nuevo_ticket["id"], msg="recurrence_created"))

@app.route("/tickets/<int:id>/trazabilidad")
def ticket_audit_trail_route(id):
    """Consulta cronológica completa de qué ocurrió, quién intervino y cuándo (HU-11)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    ticket = TicketModel.get_by_id(id)
    if not ticket:
        abort(404)

    if not TicketModel.user_can_view(user, ticket):
        return render_template(
            "errors/403.html",
            user=user,
            title="Acceso Denegado (403)",
            message="No cuentas con autorización para consultar la trazabilidad y auditoría de esta atención.",
            back_url="/tickets"
        ), 403

    trail, err = TicketModel.get_full_audit_trail(id, user)
    if err:
        return render_template("errors/403.html", user=user, title="Acceso Denegado", message=err, back_url=f"/tickets/{id}"), 403

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "ticket_id": id,
            "codigo": ticket["codigo"],
            "total_eventos": len(trail),
            "eventos": trail
        })

    return redirect(url_for("ticket_detail", id=id))

@app.route("/reportes")
def reportes_dashboard():
    """Visualización ejecutiva de resumen de tickets, KPIs y semáforo preventivo (HU-12)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    if user["rol"] not in ("Admin", "Responsable"):
        return render_template(
            "errors/403.html",
            user=user,
            title="Acceso Denegado (403)",
            message="Únicamente los Encargados de TI / Responsables y Administradores tienen autorización para consultar reportes e indicadores ejecutivos.",
            back_url="/dashboard"
        ), 403

    filters = {
        "estado": request.args.get("estado"),
        "prioridad": request.args.get("prioridad"),
        "categoria": request.args.get("categoria"),
        "area_id": request.args.get("area_id"),
        "equipo_id": request.args.get("equipo_id"),
        "fecha_desde": request.args.get("fecha_desde"),
        "fecha_hasta": request.args.get("fecha_hasta")
    }

    summary = TicketModel.get_executive_report(user, filters)
    preventivos = summary.get("mantenimiento_preventivo", {})
    areas = AreaModel.get_all()
    equipos = EquipmentModel.get_all()
    categorias = CatalogModel.get_categories()

    return render_template(
        "reportes/dashboard.html",
        user=user,
        report=summary,
        summary=summary,
        preventivos=preventivos,
        areas=areas,
        equipos=equipos,
        categorias=categorias,
        filters=filters
    )

@app.route("/reportes/exportar-csv")
def reportes_export_csv():
    """Exportación autorizada en formato CSV verificable (HU-12)."""
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))

    if user["rol"] not in ("Admin", "Responsable"):
        abort(403)

    filters = {
        "estado": request.args.get("estado"),
        "prioridad": request.args.get("prioridad"),
        "categoria": request.args.get("categoria"),
        "area_id": request.args.get("area_id"),
        "equipo_id": request.args.get("equipo_id"),
        "fecha_desde": request.args.get("fecha_desde"),
        "fecha_hasta": request.args.get("fecha_hasta")
    }

    csv_data = TicketModel.export_tickets_to_csv(user, filters)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reporte_tickets_{timestamp}.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

# =========================================================================
# HISTORIA DE USUARIO 3: GESTIÓN DE USUARIOS (ADMIN)
# =========================================================================

@app.route("/admin/usuarios", methods=["GET", "POST"])
def admin_usuarios():
    user = get_logged_user()
    if not user:
        return redirect(url_for("login", notice="logged_out"))
    if user["rol"] != "Admin":
        return render_template(
            "errors/403.html",
            user=user,
            title="Acceso Denegado (403)",
            message="Se requiere rol de Administrador para acceder al módulo de gestión de usuarios.",
            back_url="/dashboard"
        ), 403

    if request.method == "POST":
        nombre = request.form.get("nombre_completo") or ""
        username = request.form.get("username") or ""
        email = request.form.get("email") or ""
        pwd = request.form.get("password") or ""
        rol = request.form.get("rol") or "Usuario"
        estado = request.form.get("estado") or "Activo"

        _, err = UserModel.create_user(username, email, pwd, nombre, rol, estado)
        if err:
            users = UserModel.get_all()
            return render_template(
                "admin/users.html",
                user=user,
                users=users,
                error_msg=err,
                modal_open="create",
                form_nombre=nombre,
                form_username=username,
                form_email=email,
                form_rol=rol,
                form_estado=estado
            ), 400
        return redirect(url_for("admin_usuarios", msg="user_created"))

    search = request.args.get("q")
    rol_f = request.args.get("rol")
    est_f = request.args.get("estado")
    users = UserModel.get_all(search=search, role=rol_f, status=est_f)

    msg_param = request.args.get("msg")
    success_msg = None
    if msg_param == "user_created":
        success_msg = "Usuario registrado exitosamente en el sistema."
    elif msg_param == "user_updated":
        success_msg = "Datos del usuario actualizados correctamente."
    elif msg_param == "status_changed":
        success_msg = "El estado de la cuenta fue modificado con éxito."

    return render_template(
        "admin/users.html",
        user=user,
        users=users,
        search=search or "",
        role_filter=rol_f or "",
        status_filter=est_f or "",
        success_msg=success_msg,
        error_msg=request.args.get("err")
    )

@app.route("/admin/usuarios/<int:id>/editar", methods=["POST"])
def admin_user_edit(id):
    user = get_logged_user()
    if not user or user["rol"] != "Admin":
        abort(403)

    nombre = request.form.get("nombre_completo") or ""
    username = request.form.get("username") or ""
    email = request.form.get("email") or ""
    rol = request.form.get("rol") or "Usuario"
    estado = request.form.get("estado") or "Activo"
    pwd = request.form.get("password")

    if id == user["id"] and estado == "Inactivo":
        return redirect(url_for("admin_usuarios", err="No puedes desactivar tu propia cuenta en sesión"))

    _, err = UserModel.update_user(id, username, email, nombre, rol, estado, pwd)
    if err:
        return redirect(url_for("admin_usuarios", err=err))
    return redirect(url_for("admin_usuarios", msg="user_updated"))

@app.route("/admin/usuarios/<int:id>/toggle-status", methods=["POST"])
def admin_user_toggle(id):
    user = get_logged_user()
    if not user or user["rol"] != "Admin":
        abort(403)

    if id == user["id"]:
        return redirect(url_for("admin_usuarios", err="No puedes desactivar tu propia cuenta de administrador"))

    _, err = UserModel.toggle_status(id)
    if err:
        return redirect(url_for("admin_usuarios", err=err))
    return redirect(url_for("admin_usuarios", msg="status_changed"))

# =========================================================================
# MANEJADORES DE ERROR GLOBALES
# =========================================================================

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def request_entity_too_large(e):
    user = get_logged_user()
    return render_template(
        "errors/403.html",
        user=user,
        title="Archivo Excede el Límite Permitido (413)",
        message="El archivo de evidencia adjunto excede el límite máximo permitido de 10 MB. Por favor comprima el archivo o elija un documento de menor tamaño.",
        back_url="/tickets"
    ), 413

@app.errorhandler(403)
def forbidden_error(e):
    user = get_logged_user()
    return render_template(
        "errors/403.html",
        user=user,
        title="Acceso Denegado (403)",
        message="No cuentas con los permisos requeridos para acceder a esta información o ejecutar esta acción (Control de Acceso RBAC).",
        back_url="/dashboard"
    ), 403

@app.errorhandler(404)
def not_found_error(e):
    user = get_logged_user()
    return render_template(
        "errors/404.html",
        user=user,
        title="Página no encontrada",
        message="El recurso o página solicitada no existe."
    ), 404

def open_browser_delayed(url, delay=1.2):
    """Abre el navegador web automáticamente en la pantalla de Login."""
    def _open():
        import time
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()

def print_banner_and_accounts():
    print("=" * 76)
    print(f"  {COMPANY_NAME.upper()} - {SYSTEM_NAME.upper()}")
    print("=" * 76)
    print("  USUARIO ADMINISTRADOR PREDEFINIDO:")
    print("  --------------------------------------------------------------------------")
    print("  * Correo:       admin@sistema.mx  (o usuario: admin)")
    print("  * Contraseña:   Admin123")
    print("  --------------------------------------------------------------------------")

if __name__ == "__main__":
    init_db()

    raw_args = sys.argv[1:]
    args = [a.lower() for a in raw_args]

    if "--terminal" in args or "--cli" in args or "-t" in args:
        import terminal_app
        terminal_app.main()
        sys.exit(0)

    if "--test" in args or "--tests" in args:
        from tests.run_all_tests import main as run_tests
        run_tests()
        sys.exit(0)

    login_url = f"http://{SERVER_HOST}:{SERVER_PORT}/login"
    is_interactive = sys.stdin and sys.stdin.isatty()

    if is_interactive and not any(arg in args for arg in ["--web", "-w", "--noweb"]):
        print_banner_and_accounts()
        print("  Seleccione el modo de ejecución:")
        print("   [1] Servidor Web Flask (Inicia en http://127.0.0.1:5000 y abre pantalla de login)")
        print("   [2] Terminal Local / Consola (Iniciar sesión y operar en esta terminal)")
        print("   [3] Ejecutar Pruebas SPRINT 1 (HU-01 a HU-03: Seguridad, Roles y Usuarios)")
        print("   [4] Ejecutar Pruebas SPRINT 2 (HU-04 a HU-06: Catálogos, Equipos, Solicitudes y Filtros)")
        print("   [5] Ejecutar Pruebas SPRINT 3 (HU-07 a HU-09: Atención, FSM, Tiempos y Bitácora)")
        print("   [6] Ejecutar Pruebas SPRINT 4 (HU-10 a HU-12: Cierre, Trazabilidad, Reportes y CSV)")
        print("   [7] Ejecutar Pruebas de TODOS los Sprints (HU-01 a HU-12)")
        print("  --------------------------------------------------------------------------")
        choice = input("  Opción [1-7] (Presione ENTER para Servidor Web): ").strip()

        if choice == "2":
            import terminal_app
            terminal_app.main()
            sys.exit(0)
        elif choice == "3":
            from tests.run_sprint_1 import main as run_s1
            run_s1()
            sys.exit(0)
        elif choice == "4":
            from tests.run_sprint_2 import main as run_s2
            run_s2()
            sys.exit(0)
        elif choice == "5":
            from tests.run_sprint_3 import main as run_s3
            run_s3()
            sys.exit(0)
        elif choice == "6":
            from tests.run_sprint_4 import main as run_s4
            run_s4()
            sys.exit(0)
        elif choice == "7":
            from tests.run_all_tests import main as run_tests
            run_tests()
            sys.exit(0)

    # Modo Servidor Web Flask
    print_banner_and_accounts()
    print(f"  [WEB]: Servidor Flask iniciado en: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"  [LOGIN]: Pantalla de autenticación disponible en: {login_url}")
    print("  [NOTA]: Para interactuar desde la consola, ejecute: python terminal_app.py")
    print("  [CONTROL]: Presione CTRL+C en esta terminal para detener el servidor.")
    print("=" * 76 + "\n")

    open_browser_delayed(login_url)

    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)
