import os
import sys
import io
import time
from pathlib import Path

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
from models.equipment import EquipmentModel
from models.ticket import TicketModel, MAX_CONTENT_LENGTH

class MockFile:
    def __init__(self, filename, content_bytes, content_type="application/pdf"):
        self.filename = filename
        self.stream = io.BytesIO(content_bytes)
        self.content_type = content_type

    def read(self, *args):
        return self.stream.read(*args)

    def seek(self, *args):
        return self.stream.seek(*args)

def test_historia_usuario_9():
    print("\n" + "=" * 70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 9: COMENTARIOS Y EVIDENCIAS")
    print("=" * 70)

    init_db(force_reset=True)
    app.config["TESTING"] = True
    client = app.test_client()

    admin_user = UserModel.get_by_identifier("admin@sistema.mx")
    tec_asignado, _ = UserModel.create_user("tec_luis", "luis@sistema.mx", "Clave123", "Luis Técnico", "Responsable", "Activo")
    tec_ajeno, _ = UserModel.create_user("tec_ajeno", "ajeno@sistema.mx", "Clave123", "Ramiro Otro Técnico", "Responsable", "Activo")
    user_creador, _ = UserModel.create_user("sol_marta", "marta@sistema.mx", "Clave123", "Marta Solicitante", "Usuario", "Activo")
    user_intruso, _ = UserModel.create_user("sol_intruso", "intruso@sistema.mx", "Clave123", "Intruso No Autorizado", "Usuario", "Activo")

    eq = EquipmentModel.get_active()[0]

    # Crear ticket base
    ticket, _ = TicketModel.create_ticket(
        titulo="Ruido anormal en rodamiento de motor principal",
        situacion_problema="Vibración excesiva al arrancar línea 1.",
        detector_nombre="Operario Marta",
        equipo_id=eq["id"],
        categoria="Mecánica y Neumática",
        prioridad="Media",
        solicitante_id=user_creador["id"],
        responsable_id=tec_asignado["id"]
    )
    ticket_id = ticket["id"]

    # [TEST 9.1] Participantes autorizados pueden comentar (Admin, Técnico Asignado, Creador)
    print("[TEST 9.1] Probando comentarios de participantes autorizados...")
    
    # 1. Comentario del solicitante creador
    c1, err1 = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=user_creador,
        comentario="Nota inicial del solicitante: El ruido comenzó al inicio del turno matutino."
    )
    assert c1 is not None and err1 is None, f"Error al comentar como creador: {err1}"
    print(" -> Creador (Usuario) comentó exitosamente.")

    # 2. Comentario del técnico asignado
    c2, err2 = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=tec_asignado,
        comentario="Nota del técnico: Inspección visual completada, se requiere reemplazo de rodamiento SKF 6205."
    )
    assert c2 is not None and err2 is None, f"Error al comentar como técnico asignado: {err2}"
    print(" -> Técnico asignado (Responsable) comentó exitosamente.")

    # 3. Comentario del Administrador
    c3, err3 = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=admin_user,
        comentario="Nota del Administrador: Refacción aprobada con orden de compra OC-8821."
    )
    assert c3 is not None and err3 is None, f"Error al comentar como Admin: {err3}"
    print(" -> Administrador comentó exitosamente.")

    # [TEST 9.2] Bloqueo de usuarios no autorizados (otro técnico no asignado y otro solicitante)
    print("[TEST 9.2] Verificando bloqueo estricto de usuarios ajenos al ticket...")
    c_bloq1, err_bloq1 = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=tec_ajeno,
        comentario="Intento de intromisión por técnico no asignado."
    )
    assert c_bloq1 is None, "Técnico no asignado NO debe poder comentar"
    assert "403" in err_bloq1 or "denegada" in err_bloq1.lower()
    print(" -> Técnico no asignado bloqueado con 403.")

    c_bloq2, err_bloq2 = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=user_intruso,
        comentario="Intento de intromisión por usuario ajeno."
    )
    assert c_bloq2 is None, "Usuario no creador NO debe poder comentar"
    assert "403" in err_bloq2 or "denegada" in err_bloq2.lower()
    print(" -> Usuario ajeno bloqueado con 403.")

    # [TEST 9.3] Inmutabilidad de autor y fecha y orden cronológico
    print("[TEST 9.3] Validando inmutabilidad de autor, fecha y orden cronológico...")
    historial = TicketModel.get_history(ticket_id)
    # Debe contener la creación del ticket y luego los 3 comentarios en estricto orden
    comentarios_hist = [h for h in historial if "Comentario" in h["accion"]]
    assert len(comentarios_hist) == 3, f"Se esperaban 3 comentarios, se encontraron {len(comentarios_hist)}"

    assert comentarios_hist[0]["usuario_id"] == user_creador["id"]
    assert comentarios_hist[0]["usuario_nombre"] == "Marta Solicitante"
    assert comentarios_hist[0]["created_at"] is not None

    assert comentarios_hist[1]["usuario_id"] == tec_asignado["id"]
    assert comentarios_hist[1]["usuario_nombre"] == "Luis Técnico"

    assert comentarios_hist[2]["usuario_id"] == admin_user["id"]
    assert comentarios_hist[2]["usuario_nombre"] == "Administrador del Sistema"

    # Verificar orden ascendente por ID
    ids = [h["id"] for h in historial]
    assert ids == sorted(ids), "El historial debe conservar orden cronológico ascendente estricto"
    print(" -> Inmutabilidad de autor y fecha y orden cronológico validados 100%.")

    # [TEST 9.4] Adjuntos dentro del límite (<= 10 MB) y rechazo de archivos excedidos
    print("[TEST 9.4] Verificando adjuntos con control estricto de tamaño <= 10 MB...")
    # 1. Archivo válido (500 KB)
    val_data = b"%PDF-1.4 Mock technical report content" * 15000
    mock_val = MockFile("informe_tecnico_rodamiento.pdf", val_data, "application/pdf")
    c_adj, err_adj = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=tec_asignado,
        comentario="Se adjunta reporte termográfico y hoja de datos del rodamiento",
        archivo=mock_val
    )
    assert c_adj is not None, f"Error al adjuntar archivo válido: {err_adj}"
    print(" -> Archivo técnico válido adjuntado e indexado en el historial.")

    # 2. Archivo excedido (> 10 MB) con extensión autorizada
    large_data = b"0" * (MAX_CONTENT_LENGTH + 1024)
    mock_large = MockFile("documento_pesado.zip", large_data, "application/zip")
    c_exc, err_exc = TicketModel.add_comment(
        ticket_id=ticket_id,
        user=tec_asignado,
        comentario="Intento de subir archivo superior a 10 MB",
        archivo=mock_large
    )
    assert c_exc is None, "Debe rechazar archivos de más de 10 MB"
    assert "10 mb" in err_exc.lower(), f"Mensaje incorrecto: {err_exc}"
    print(" -> Archivo de más de 10 MB rechazado correctamente con validación de límite.")

    # [TEST 9.5] Pruebas de acceso y descarga segura (HTTP 200 para autorizados, 403 para ajenos)
    print("[TEST 9.5] Verificando permisos de acceso y descarga vía Flask...")
    adjuntos = TicketModel.get_attachments(ticket_id)
    assert len(adjuntos) >= 1, "Debe existir al menos un archivo adjunto"
    adj_id = adjuntos[-1]["id"]

    # 1. Descarga como Administrador -> 200 OK
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user["id"]
        sess["user_name"] = admin_user["nombre_completo"]
        sess["user_role"] = admin_user["rol"]
    res_adm = client.get(f"/tickets/adjuntos/{adj_id}")
    assert res_adm.status_code == 200, f"Admin debe poder descargar adjuntos, código: {res_adm.status_code}"

    # 2. Descarga como Técnico asignado -> 200 OK
    with client.session_transaction() as sess:
        sess["user_id"] = tec_asignado["id"]
        sess["user_name"] = tec_asignado["nombre_completo"]
        sess["user_role"] = tec_asignado["rol"]
    res_tec = client.get(f"/tickets/adjuntos/{adj_id}")
    assert res_tec.status_code == 200, f"Técnico asignado debe poder descargar adjuntos, código: {res_tec.status_code}"

    # 3. Descarga como Solicitante creador -> 200 OK
    with client.session_transaction() as sess:
        sess["user_id"] = user_creador["id"]
        sess["user_name"] = user_creador["nombre_completo"]
        sess["user_role"] = user_creador["rol"]
    res_cre = client.get(f"/tickets/adjuntos/{adj_id}")
    assert res_cre.status_code == 200, f"Solicitante creador debe poder descargar adjuntos, código: {res_cre.status_code}"

    # 4. Intento de descarga por usuario no autorizado (intruso) -> 403 Forbidden
    with client.session_transaction() as sess:
        sess["user_id"] = user_intruso["id"]
        sess["user_name"] = user_intruso["nombre_completo"]
        sess["user_role"] = user_intruso["rol"]
    res_int = client.get(f"/tickets/adjuntos/{adj_id}")
    assert res_int.status_code == 403, f"Usuario no autorizado debe recibir 403, recibido: {res_int.status_code}"

    # 5. Intento de descarga por técnico no asignado -> 403 Forbidden
    with client.session_transaction() as sess:
        sess["user_id"] = tec_ajeno["id"]
        sess["user_name"] = tec_ajeno["nombre_completo"]
        sess["user_role"] = tec_ajeno["rol"]
    res_tec_aj = client.get(f"/tickets/adjuntos/{adj_id}")
    assert res_tec_aj.status_code == 403, f"Técnico no asignado debe recibir 403, recibido: {res_tec_aj.status_code}"
    print(" -> Descarga segura verificada: participantes autorizados obtienen 200 OK y ajenos reciben 403 Forbidden.")

    print("=" * 70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 9 VERIFICADOS EXITOSAMENTE!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_9()

