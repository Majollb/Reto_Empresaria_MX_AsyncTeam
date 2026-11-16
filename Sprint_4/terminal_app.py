import os
import sys
import webbrowser
import threading
from pathlib import Path

# Asegurar importaciones del proyecto
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Carga de site-packages de usuario para garantizar disponibilidad de dependencias
site_packages_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for sp in site_packages_candidates:
    if sp.is_dir() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))

from config import COMPANY_NAME, SYSTEM_NAME, SERVER_HOST, SERVER_PORT
from database.db import init_db
from models.user import UserModel
from models.ticket import TicketModel
from models.equipment import EquipmentModel, AreaModel, CatalogModel
from auth.security import verify_password

AUTH_ERROR_MSG = "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa. Contacte al administrador."
LOGOUT_NOTICE_MSG = "Tu sesión ha finalizado correctamente. Por seguridad, debes volver a autenticarte para acceder a páginas protegidas."

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_header(title=""):
    print("=" * 80)
    print(f"  {COMPANY_NAME.upper()} - {SYSTEM_NAME.upper()}")
    if title:
        print(f"  >>> {title}")
    print("=" * 80)

def format_table(headers, rows):
    """Imprime una tabla de texto alineada con bordes limpios."""
    if not rows:
        print("  (No hay registros para mostrar)")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print("  " + header_str)
    print("  " + sep_str)

    for row in rows:
        row_str = " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row))
        print("  " + row_str)

def launch_web_server():
    """Inicia el servidor web Flask en segundo plano y abre el navegador en el Login."""
    print("\n  [INFO] Iniciando servidor web Flask...")
    def run_server():
        try:
            from app import app
            app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)
        except Exception as e:
            print(f"\n  [ERROR AL INICIAR FLASK]: {e}")

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    url = f"http://{SERVER_HOST}:{SERVER_PORT}/login"
    print(f"  [INFO] Servidor web activo en: {url}")
    print("  [INFO] Abriendo pantalla de Login en el navegador web...")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    input("\n  Presione ENTER para continuar en la consola...")

class TerminalSession:
    def __init__(self):
        self.user = None
        self.notice = None

    def login_menu(self):
        while not self.user:
            clear_screen()
            print_header("MÓDULO DE ACCESO Y AUTENTICACIÓN (LOGIN LOCAL)")

            if self.notice:
                print(f"\n  [AVISO]: {self.notice}\n")
                self.notice = None

            print("  Por favor, ingrese sus credenciales para autenticarse:")
            print("  ----------------------------------------------------------------------")
            print("  (Usuario administrador predeterminado: admin@sistema.mx / Admin123)")
            print("  ----------------------------------------------------------------------")

            identificador = input("  Identificador (Correo o Usuario): ").strip()
            if not identificador:
                continue

            password = input("  Contraseña: ").strip()

            target_user = UserModel.get_by_identifier(identificador)
            is_valid = False
            if target_user:
                pwd_matches = verify_password(password, target_user["password_hash"], target_user["salt"])
                is_active = (target_user["estado"] == "Activo")
                if pwd_matches and is_active:
                    is_valid = True
            else:
                # Opción para crear el usuario en caso de que no exista con rol Usuario por defecto
                print(f"\n  [AVISO]: El identificador '{identificador}' no existe en el sistema.")
                crear = input("  ¿Deseas registrar este usuario con el rol por defecto 'Usuario'? (s/n): ").strip().lower()
                if crear in ('s', 'si', 'y', 'yes'):
                    nombre = input("  Ingrese su Nombre Completo: ").strip()
                    new_u, err = UserModel.register_user(identificador, password, nombre)
                    if new_u:
                        print(f"\n  [ÉXITO]: Usuario '{new_u['nombre_completo']}' creado exitosamente con rol [{new_u['rol']}].")
                        input("  Presione ENTER para continuar...")
                        self.user = new_u
                        break
                    else:
                        print(f"\n  [ERROR]: {err}")
                        input("\n  Presione ENTER para continuar...")
                        continue

            if not is_valid:
                print(f"\n  [ERROR]: {AUTH_ERROR_MSG}")
                input("\n  Presione ENTER para reintentar...")
            else:
                self.user = target_user
                break

    def logout(self):
        self.user = None
        self.notice = LOGOUT_NOTICE_MSG

    def run(self):
        init_db()
        while True:
            if not self.user:
                self.login_menu()

            clear_screen()
            user = UserModel.get_by_id(self.user["id"])
            if not user or user.get("estado") != "Activo":
                print("\n  [ALERTA DE SEGURIDAD]: La cuenta ha sido desactivada o no es válida.")
                self.logout()
                continue
            self.user = user

            print_header(f"SESIÓN ACTIVA | Usuario: {self.user['nombre_completo']} | Rol: {self.user['rol']}")
            print("  MENÚ PRINCIPAL:")
            print("  ----------------------------------------------------------------------")
            print("  [1] Ver Dashboard (Métricas y resumen de incidencias)")
            print("  [2] Listar y Filtrar Tickets (HU-06: por Folio, Equipo, Estado, Prioridad)")
            print("  [3] Consultar Detalle de un Ticket (HU-06: Equipo vinculado y Evidencias)")
            print("  [4] Registrar Solicitud de Ticket con Equipo Activo (HU-05)")
            print("  [5] Consultar Catálogo de Equipos e Inventario (HU-04)")
            if self.user["rol"] == "Admin":
                print("  [6] Mantenimiento de Equipos y Áreas (Admin - HU-04)")
                print("  [7] Reasignar Técnico Responsable a Ticket (Admin)")
                print("  [8] Módulo de Gestión de Usuarios (Admin - HU-03)")
            print("  [9] Cambiar Estado / Comentar en un Ticket")
            print("  [W] Abrir Servidor Web Flask en el Navegador")
            print("  [0] Cerrar Sesión (Logout)")
            print("  ----------------------------------------------------------------------")

            op = input("  Seleccione una opción: ").strip().upper()

            if op == "1":
                self.view_dashboard()
            elif op == "2":
                self.view_tickets()
            elif op == "3":
                self.view_ticket_detail()
            elif op == "4":
                self.create_ticket()
            elif op == "5":
                self.view_equipos()
            elif op == "6" and self.user["rol"] == "Admin":
                self.manage_catalogs()
            elif op == "7" and self.user["rol"] == "Admin":
                self.reassign_ticket()
            elif op == "8" and self.user["rol"] == "Admin":
                self.manage_users()
            elif op == "9":
                self.update_or_comment_ticket()
            elif op == "W":
                launch_web_server()
            elif op == "0":
                self.logout()
            else:
                input("\n  Opción no reconocida o no permitida para su rol. Presione ENTER...")

    def view_dashboard(self):
        clear_screen()
        print_header("PANEL PRINCIPAL (DASHBOARD)")
        stats = TicketModel.get_stats_for_user(self.user)
        recent_tickets = TicketModel.get_tickets_for_user(self.user)[:6]

        print(f"\n  Información del Usuario Conectado:")
        print(f"  - Nombre:     {self.user['nombre_completo']}")
        print(f"  - Rol:        {self.user['rol']}")
        print(f"  - Correo:     {self.user['email']}")
        print(f"  - Estado:     {self.user['estado']}")

        print("\n  Métricas de Incidencias:")
        print("  +-----------------+-----------------+-----------------+-----------------+")
        print(f"  | Total: {str(stats.get('total', 0)).ljust(8)} | Abiertos: {str(stats.get('abiertos', 0)).ljust(5)} | En Proc: {str(stats.get('en_proceso', 0)).ljust(6)} | Resueltos: {str(stats.get('resueltos', 0)).ljust(4)} |")
        print("  +-----------------+-----------------+-----------------+-----------------+")

        print("\n  Tickets Recientes:")
        headers = ["Código", "Título", "Equipo", "Estado", "Prioridad", "Solicitante"]
        rows = []
        for t in recent_tickets:
            rows.append([
                t["codigo"],
                t["titulo"][:24],
                t.get("equipo_codigo") or "N/A",
                t["estado"],
                t["prioridad"],
                t.get("solicitante_nombre", "-")[:16]
            ])
        format_table(headers, rows)
        input("\n  Presione ENTER para regresar al menú principal...")

    def view_tickets(self):
        clear_screen()
        print_header("LISTADO Y FILTRADO AVANZADO DE TICKETS (HU-06)")
        print("  Filtros disponibles (deje en blanco para omitir):")
        folio = input("  - Buscar por Folio o Código exacto/parcial: ").strip() or None
        search = input("  - Buscar palabra clave en título/situación/equipo: ").strip() or None
        estado = input("  - Filtrar por estado (Abierto, En Proceso, En Espera, Resuelto, Cerrado): ").strip() or None
        prioridad = input("  - Filtrar por prioridad (Baja, Media, Alta, Urgente): ").strip() or None

        ticket_list = TicketModel.get_tickets_for_user(
            self.user, search=search, folio=folio, estado=estado, prioridad=prioridad
        )

        print(f"\n  Resultados encontrados: {len(ticket_list)}")
        if not ticket_list:
            print("  [AVISO]: No se encontraron tickets con los criterios de búsqueda seleccionados.")
        else:
            headers = ["Folio", "Título", "Equipo Vinculado", "Área", "Estado", "Prioridad", "Solicitante"]
            rows = []
            for t in ticket_list:
                rows.append([
                    t["codigo"],
                    t["titulo"][:22],
                    f"{t.get('equipo_codigo') or ''} - {t.get('equipo_nombre') or ''}"[:20],
                    (t.get("area_nombre") or "")[:15],
                    t["estado"],
                    t["prioridad"],
                    (t.get("solicitante_nombre") or "")[:14]
                ])
            format_table(headers, rows)
        input("\n  Presione ENTER para regresar al menú principal...")

    def view_ticket_detail(self):
        clear_screen()
        print_header("CONSULTAR DETALLE COHERENTE DE UN TICKET (HU-06)")
        val = input("  Ingrese el ID numérico o el Folio del ticket (ej: 1 o TK-2026-001): ").strip()
        if not val:
            return

        ticket = TicketModel.get_by_id(int(val)) if val.isdigit() else TicketModel.get_by_codigo(val)

        if not ticket:
            print(f"\n  [ERROR 404]: No se encontró ningún ticket con el identificador '{val}'.")
            input("\n  Presione ENTER para continuar...")
            return

        if not TicketModel.user_can_view(self.user, ticket):
            print("\n  " + "!" * 74)
            print("  [ERROR 403 - ACCESO DENEGADO]:")
            print("  No tienes autorización para consultar la información de este ticket.")
            print("  Solo el solicitante, el técnico asignado o un Administrador tienen acceso.")
            print("  " + "!" * 74)
            input("\n  Presione ENTER para continuar...")
            return

        clear_screen()
        print_header(f"FOLIO: {ticket['codigo']} | {ticket['titulo']}")
        print(f"  - Estado:               [{ticket['estado']}]")
        print(f"  - Prioridad:            {ticket['prioridad']}")
        print(f"  - Categoría:            {ticket['categoria']}")
        print(f"  - Solicitante:          {ticket.get('solicitante_nombre')} ({ticket.get('solicitante_email')})")
        print(f"  - Detectado Por:        {ticket.get('detector_nombre') or 'Mismo solicitante'}")
        print(f"  - Responsable Asignado: {ticket.get('responsable_nombre') or 'Sin asignar'}")
        print(f"  - Fecha de Registro:    {ticket.get('created_at')}")

        if ticket.get("ticket_relacionado_codigo"):
            print(f"  - Ticket Relacionado:   {ticket.get('ticket_relacionado_codigo')} (Duplicado)")
        if ticket.get("motivo_espera"):
            print(f"  - Motivo de Espera:     {ticket.get('motivo_espera')}")
        if ticket.get("motivo_cancelacion"):
            print(f"  - Motivo Cancelación:   {ticket.get('motivo_cancelacion')}")

        # Métricas de tiempo (HU-08)
        metrics = ticket.get("metricas_tiempo", {})
        if metrics:
            print("\n  MÉTRICAS DE TIEMPO Y DISTINCIÓN DE ESPERAS (HU-08):")
            print("  ----------------------------------------------------------------------")
            print(f"  * Lead Time Total:      {metrics.get('tiempo_total_texto', 'N/D')}")
            print(f"  * Tiempo en Pausa:      {metrics.get('tiempo_espera_texto', '0 min')}")
            print(f"  * Tiempo Neto Atención: {metrics.get('tiempo_neto_texto', 'N/D')}")

        print("\n  INFORMACIÓN DEL EQUIPO INDUSTRIAL VINCULADO (HU-04):")
        print("  ----------------------------------------------------------------------")
        if ticket.get("equipo_nombre"):
            print(f"  * Código y Nombre:      {ticket.get('equipo_codigo')} - {ticket.get('equipo_nombre')}")
            print(f"  * Marca y Modelo:       {ticket.get('equipo_marca')} {ticket.get('equipo_modelo')}")
            print(f"  * Número de Serie:      {ticket.get('equipo_serie')}")
            print(f"  * Área y Localización:  {ticket.get('area_nombre')} ({ticket.get('equipo_ubicacion_esp') or ticket.get('ubicacion_equipo')})")
            print(f"  * Periodicidad:         Cada {ticket.get('equipo_periodicidad')} días (Último mant.: {ticket.get('equipo_ultimo_mant') or 'N/A'})")
            print(f"  * Estado del Equipo:    [{ticket.get('equipo_estado')}]")
        else:
            print("  * Sin equipo específico vinculado.")

        print("\n  SITUACIÓN Y DESCRIPCIÓN DE LA FALLA (HU-05):")
        print(f"  {ticket.get('situacion_problema') or ticket.get('descripcion')}")

        print("\n  EVIDENCIAS TÉCNICAS ADJUNTAS (HU-05: <= 10 MB):")
        if ticket.get("adjuntos"):
            for a in ticket["adjuntos"]:
                print(f"  * Archivo: {a['nombre_original']} ({a['tamano_formateado']}) - Subido: {a['created_at']}")
        else:
            print("  (Sin evidencias adjuntas)")

        print("\n  BITÁCORA DE HISTORIAL Y NOTAS:")
        history = TicketModel.get_history(ticket["id"])
        if history:
            for h in history:
                print(f"  * [{h['created_at']}] {h['usuario_nombre']} ({h['accion']}): {h.get('comentario') or ''}")
        else:
            print("  (Sin historial)")

        input("\n  Presione ENTER para regresar...")

    def create_ticket(self):
        clear_screen()
        print_header("REGISTRAR SOLICITUD DE TICKET CON EQUIPO ACTIVO (HU-05)")

        # Listar equipos activos
        activos = EquipmentModel.get_active()
        if not activos:
            print("\n  [ERROR]: No hay equipos activos disponibles en el catálogo.")
            input("  Presione ENTER..."); return

        print("  Equipos Activos Disponibles (HU-05):")
        for i, eq in enumerate(activos, start=1):
            print(f"   [{i}] {eq['codigo']} - {eq['nombre']} ({eq['area_nombre']})")

        eq_choice = input(f"\n  Seleccione el equipo activo [1-{len(activos)}]: ").strip()
        if not eq_choice.isdigit() or not (1 <= int(eq_choice) <= len(activos)):
            print("\n  [ERROR]: Selección de equipo inválida.")
            input("  Presione ENTER..."); return

        selected_eq = activos[int(eq_choice) - 1]

        titulo = input("\n  Título de la solicitud/incidencia: ").strip()
        if not titulo or len(titulo) < 5:
            print("\n  [ERROR]: El título es obligatorio y debe contener al menos 5 caracteres.")
            input("  Presione ENTER..."); return

        detector = input("  Persona o turno que detectó la falla: ").strip() or self.user["nombre_completo"]

        situacion = input("  Situación o descripción detallada de la anomalía: ").strip()
        if not situacion or len(situacion) < 10:
            print("\n  [ERROR]: La descripción de la situación debe contener al menos 10 caracteres.")
            input("  Presione ENTER..."); return

        print("\n  Prioridad: [1] Baja  [2] Media  [3] Alta  [4] Urgente")
        pri_map = {"1": "Baja", "2": "Media", "3": "Alta", "4": "Urgente"}
        prioridad = pri_map.get(input("  Seleccione prioridad [1-4] (Defecto: 2): ").strip(), "Media")

        print("\n  Categoría: [1] Automatización  [2] Preventivo  [3] Correctivo  [4] Eléctrico  [5] Mecánico")
        cat_map = {
            "1": "Automatización Industrial", "2": "Mantenimiento Preventivo",
            "3": "Mantenimiento Correctivo", "4": "Electricidad y Fuerza", "5": "Mecánica y Neumática"
        }
        categoria = cat_map.get(input("  Seleccione categoría [1-5] (Defecto: 1): ").strip(), "Automatización Industrial")

        ubicacion = input(f"  Ubicación específica (dejar vacío para '{selected_eq['ubicacion_especifica']}'): ").strip() or selected_eq["ubicacion_especifica"]

        new_t, err = TicketModel.create_ticket(
            titulo=titulo,
            situacion_problema=situacion,
            detector_nombre=detector,
            equipo_id=selected_eq["id"],
            categoria=categoria,
            prioridad=prioridad,
            solicitante_id=self.user["id"],
            ubicacion_equipo=ubicacion
        )

        if err:
            print(f"\n  [ERROR AL REGISTRAR TICKET]: {err}")
        else:
            print(f"\n  [ÉXITO]: Solicitud registrada con Folio Único: {new_t['codigo']} (ID: {new_t['id']})")
            print(f"  Equipo Vinculado: {selected_eq['codigo']} - {selected_eq['nombre']}")
        input("\n  Presione ENTER para continuar...")

    def view_equipos(self):
        clear_screen()
        print_header("CATÁLOGO DE EQUIPOS E INVENTARIO INDUSTRIAL (HU-04)")
        equipos = EquipmentModel.get_all()
        headers = ["Código", "Equipo", "Marca", "Serie", "Área", "Periodicidad", "Último Mant.", "Estado"]
        rows = []
        for eq in equipos:
            rows.append([
                eq["codigo"],
                eq["nombre"][:20],
                eq["marca"][:12],
                eq["numero_serie"][:14],
                eq["area_nombre"][:15],
                f"{eq['periodicidad_dias']} días",
                eq["fecha_ultimo_mantenimiento"] or "N/A",
                eq["estado"]
            ])
        format_table(headers, rows)
        input("\n  Presione ENTER para regresar...")

    def manage_catalogs(self):
        clear_screen()
        print_header("GESTIÓN DE EQUIPOS Y ÁREAS (ADMIN - HU-04)")
        print("  [1] Registrar Nuevo Equipo Industrial")
        print("  [2] Activar / Desactivar Equipo (Conserva referencias históricas)")
        print("  [3] Registrar Nueva Área Industrial")
        print("  [4] Activar / Desactivar Área")
        print("  [0] Volver")
        sub_op = input("\n  Opción: ").strip()

        if sub_op == "1":
            clear_screen()
            print_header("NUEVO EQUIPO INDUSTRIAL")
            codigo = input("  Código único (ej: EQ-CNC-009): ").strip().upper()
            nombre = input("  Nombre del equipo: ").strip()
            marca = input("  Marca: ").strip()
            modelo = input("  Modelo: ").strip()
            serie = input("  Número de serie: ").strip()
            
            areas = AreaModel.get_all(active_only=True)
            for a in areas:
                print(f"   [{a['id']}] {a['nombre']}")
            area_id = int(input("  ID del área: ").strip())
            ubic = input("  Ubicación específica: ").strip()
            per = int(input("  Periodicidad preventiva en días (ej: 60): ").strip() or 90)
            f_ult = input("  Fecha último mantenimiento (YYYY-MM-DD): ").strip() or None

            eq, err = EquipmentModel.create_equipment(
                codigo, nombre, marca, modelo, serie, area_id, ubic, per, f_ult
            )
            if err:
                print(f"\n  [ERROR]: {err}")
            else:
                print(f"\n  [ÉXITO]: Equipo {eq['codigo']} registrado correctamente.")
            input("  Presione ENTER...")

        elif sub_op == "2":
            clear_screen()
            print_header("ACTIVAR / DESACTIVAR EQUIPO")
            eqs = EquipmentModel.get_all()
            for eq in eqs:
                print(f"  [{eq['id']}] {eq['codigo']} - {eq['nombre']} (Estado: {eq['estado']})")
            val = input("\n  ID de equipo a alternar estado: ").strip()
            if val.isdigit():
                eq, err = EquipmentModel.toggle_status(int(val))
                if err:
                    print(f"  [ERROR]: {err}")
                else:
                    print(f"  [ÉXITO]: Equipo {eq['codigo']} ahora está [{eq['estado']}]. Referencias históricas preservadas.")
            input("  Presione ENTER...")

    def update_or_comment_ticket(self):
        clear_screen()
        print_header("ACTUALIZAR ESTADO O COMENTAR EN TICKET")
        val = input("  Ingrese ID del ticket: ").strip()
        if not val.isdigit():
            return
        ticket_id = int(val)
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket or not TicketModel.user_can_view(self.user, ticket):
            print("\n  [ERROR]: Ticket no encontrado o acceso no autorizado."); input("  Presione ENTER..."); return

        print(f"\n  Ticket #{ticket['id']} ({ticket['codigo']}): {ticket['titulo']}")
        print(f"  Estado actual: [{ticket['estado']}]")
        print("  [1] Cambiar Estado")
        print("  [2] Agregar Comentario / Nota de Seguimiento")
        acc = input("  Opción: ").strip()

        if acc == "1":
            if not TicketModel.user_can_modify(self.user, ticket):
                print("\n  [ERROR 403]: No tienes permisos para modificar el estado."); input("  Presione ENTER..."); return
            print("  Estados permitidos:")
            print("  [1] Abierto  [2] En Proceso  [3] En Espera  [4] Resuelto  [5] Cerrado  [6] Cancelado  [7] Duplicado")
            st_map = {
                "1": "Abierto", "2": "En Proceso", "3": "En Espera",
                "4": "Resuelto", "5": "Cerrado", "6": "Cancelado", "7": "Duplicado"
            }
            new_st = st_map.get(input("  Nuevo estado [1-7]: ").strip())
            if new_st:
                com = input("  Comentario / Justificación de la transición: ").strip()
                rel_id = None
                if new_st == "Duplicado":
                    rel_input = input("  ID o Folio del ticket original relacionado: ").strip()
                    if rel_input.isdigit():
                        rel_id = int(rel_input)
                    else:
                        rel_t = TicketModel.get_by_codigo(rel_input)
                        if rel_t:
                            rel_id = rel_t["id"]
                ok, err = TicketModel.update_status(ticket_id, new_st, self.user, com, ticket_relacionado_id=rel_id)
                if ok:
                    print(f"\n  [ÉXITO]: Estado actualizado a [{new_st}].")
                else:
                    print(f"\n  [ERROR]: {err}")
            input("  Presione ENTER...")
        elif acc == "2":
            com = input("\n  Escriba nota o comentario técnico: ").strip()
            if com:
                ok, err = TicketModel.add_comment(ticket_id, self.user, com)
                if ok:
                    print("\n  [ÉXITO]: Comentario registrado con autor y fecha inmutables (HU-09).")
                else:
                    print(f"\n  [ERROR]: {err}")
            input("  Presione ENTER...")

    def reassign_ticket(self):
        clear_screen()
        print_header("REASIGNAR RESPONSABLE TÉCNICO (ADMIN)")
        val = input("  Ingrese ID del ticket: ").strip()
        if not val.isdigit():
            return
        ticket_id = int(val)
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            print("  Ticket no encontrado."); input("  Presione ENTER..."); return

        responsables = UserModel.get_all(role="Responsable", status="Activo")
        print("\n  Técnicos responsables activos:")
        print("   [0] Sin asignar")
        for r in responsables:
            print(f"   [{r['id']}] {r['nombre_completo']}")
        raw_r = input("\n  Seleccione ID de nuevo responsable: ").strip()
        if raw_r.isdigit():
            resp_id = int(raw_r) if raw_r != "0" else None
            motivo = input("  Motivo de asignación/reasignación (obligatorio si ya tenía responsable): ").strip()
            ok, err = TicketModel.reassign_responsable(ticket_id, resp_id, self.user, motivo)
            if ok:
                print("\n  [ÉXITO]: Responsable actualizado y registrado en auditoría (HU-07).")
            else:
                print(f"\n  [ERROR]: {err}")
        input("  Presione ENTER...")

    def manage_users(self):
        clear_screen()
        print_header("GESTIÓN DE USUARIOS (ADMIN - HU-03)")
        users = UserModel.get_all()
        headers = ["ID", "Usuario", "Email", "Nombre", "Rol", "Estado"]
        rows = [[u["id"], u["username"], u["email"], u["nombre_completo"][:18], u["rol"], u["estado"]] for u in users]
        format_table(headers, rows)
        input("\n  Presione ENTER para regresar...")

def main():
    session = TerminalSession()
    session.run()

if __name__ == "__main__":
    main()
