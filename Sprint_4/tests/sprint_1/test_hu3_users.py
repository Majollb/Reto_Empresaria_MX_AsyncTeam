import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

site_candidates = [
    Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / "Python313" / "site-packages",
    Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages",
    Path(r"C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\Lib\site-packages")
]
for p in site_candidates:
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app import app
from database.db import init_db
from models.user import UserModel

def test_historia_usuario_3():
    print("\n" + "="*70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 3 (FLASK): GESTIÓN DE USUARIOS")
    print("="*70)

    init_db(force_reset=True)
    app.config["TESTING"] = True

    client_admin = app.test_client()
    client_admin.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})

    # 1. Registrar nuevo usuario con rol y estado
    print("\n[TEST 3.1] Administrador registra nuevo usuario técnico (tecnico2)...")
    res_create = client_admin.post(
        "/admin/usuarios",
        data={
            "nombre_completo": "Ing. Fernando Silva",
            "username": "fsilva",
            "email": "f.silva@bajio.mx",
            "password": "PasswordTecnico123*",
            "rol": "Responsable",
            "estado": "Activo"
        },
        follow_redirects=False
    )
    assert res_create.status_code == 302
    
    new_u = UserModel.get_by_identifier("fsilva")
    assert new_u is not None
    assert new_u["nombre_completo"] == "Ing. Fernando Silva"
    assert new_u["rol"] == "Responsable"
    assert new_u["estado"] == "Activo"
    print(" -> PASÓ: Usuario registrado correctamente con rol Responsable y estado Activo.")

    # 2. Actualizar usuario existente
    print("\n[TEST 3.2] Administrador actualiza datos del usuario fsilva...")
    res_edit = client_admin.post(
        f"/admin/usuarios/{new_u['id']}/editar",
        data={
            "nombre_completo": "Ing. Fernando Silva Senior",
            "username": "fsilva",
            "email": "f.silva@bajio.mx",
            "rol": "Responsable",
            "estado": "Activo"
        },
        follow_redirects=False
    )
    assert res_edit.status_code == 302
    updated_u = UserModel.get_by_id(new_u["id"])
    assert updated_u["nombre_completo"] == "Ing. Fernando Silva Senior"
    print(" -> PASÓ: Usuario actualizado exitosamente.")

    # 3. Impedir identificadores duplicados (username y email)
    print("\n[TEST 3.3] Intento de registrar usuario con nombre de usuario duplicado ('fsilva')...")
    res_dup_user = client_admin.post(
        "/admin/usuarios",
        data={
            "nombre_completo": "Otro Usuario",
            "username": "fsilva",  # Ya existe
            "email": "otro@bajio.mx",
            "password": "Password123*",
            "rol": "Usuario",
            "estado": "Activo"
        }
    )
    assert res_dup_user.status_code == 400
    html_dup_u = res_dup_user.data.decode("utf-8")
    assert "ya está registrado" in html_dup_u or "duplicado" in html_dup_u
    print(" -> PASÓ: Registro con username duplicado impedido correctamente.")

    print("\n[TEST 3.4] Intento de registrar usuario con correo duplicado ('admin@sistema.mx')...")
    res_dup_email = client_admin.post(
        "/admin/usuarios",
        data={
            "nombre_completo": "Clon Admin",
            "username": "clonadmin",
            "email": "admin@sistema.mx",  # Ya existe
            "password": "Password123*",
            "rol": "Usuario",
            "estado": "Activo"
        }
    )
    assert res_dup_email.status_code == 400
    html_dup_e = res_dup_email.data.decode("utf-8")
    assert "ya se encuentra asignado" in html_dup_e or "duplicado" in html_dup_e
    print(" -> PASÓ: Registro con correo duplicado impedido correctamente.")

    # 4. Activar / Desactivar cuenta
    print("\n[TEST 3.5] Administrador desactiva la cuenta de 'fsilva'...")
    res_toggle_off = client_admin.post(f"/admin/usuarios/{new_u['id']}/toggle-status", follow_redirects=False)
    assert res_toggle_off.status_code == 302
    u_inactive = UserModel.get_by_id(new_u["id"])
    assert u_inactive["estado"] == "Inactivo"
    print(" -> PASÓ: Cuenta desactivada correctamente.")

    # 5. Cuenta inactiva no inicia sesión
    print("\n[TEST 3.6] Verificando que cuenta desactivada NO puede iniciar sesión...")
    client_test = app.test_client()
    res_login_inactive = client_test.post(
        "/login",
        data={"identificador": "f.silva@bajio.mx", "password": "PasswordTecnico123*"}
    )
    assert res_login_inactive.status_code == 401
    html_inact = res_login_inactive.data.decode("utf-8")
    assert "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa." in html_inact
    print(" -> PASÓ: Cuenta inactiva es rechazada en el login.")

    # Reactivar cuenta y probar que ahora sí puede entrar
    print("\n[TEST 3.7] Reactivando cuenta de 'fsilva'...")
    res_toggle_on = client_admin.post(f"/admin/usuarios/{new_u['id']}/toggle-status", follow_redirects=False)
    assert res_toggle_on.status_code == 302
    u_active = UserModel.get_by_id(new_u["id"])
    assert u_active["estado"] == "Activo"

    res_login_reactivated = client_test.post(
        "/login",
        data={"identificador": "f.silva@bajio.mx", "password": "PasswordTecnico123*"},
        follow_redirects=False
    )
    assert res_login_reactivated.status_code == 302
    assert "/dashboard" in res_login_reactivated.headers.get("Location", "")
    print(" -> PASÓ: Cuenta reactivada inicia sesión correctamente en Flask.")

    print("="*70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 3 (FLASK) VERIFICADOS EXITOSAMENTE!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_3()

