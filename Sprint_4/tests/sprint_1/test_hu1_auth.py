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

def test_historia_usuario_1():
    print("\n" + "="*70)
    print(" INICIANDO PRUEBAS DE HISTORIA DE USUARIO 1 (FLASK): AUTENTICACIÓN")
    print("="*70)

    init_db(force_reset=True)
    app.config["TESTING"] = True
    client = app.test_client()

    # Criterio 1: Activo con credenciales válidas inicia sesión
    print("[TEST 1.1] Intento de login con cuenta activa y credenciales válidas (admin@sistema.mx)...")
    res = client.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"}, follow_redirects=False)
    assert res.status_code == 302, f"Esperado 302 Found, obtenido: {res.status_code}"
    assert "/dashboard" in res.headers.get("Location", "")
    print(" -> PASÓ: Usuario activo inicia sesión en Flask y es redirigido al dashboard.")

    # Criterio 2: Credenciales inválidas no revelan cuál dato falló
    client.get("/logout")
    print("[TEST 1.2] Login con contraseña incorrecta...")
    res_bad_pwd = client.post("/login", data={"identificador": "admin@sistema.mx", "password": "ClaveIncorrecta"})
    assert res_bad_pwd.status_code == 401
    html_pwd = res_bad_pwd.data.decode("utf-8")
    assert "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa." in html_pwd

    client.get("/logout")
    print("[TEST 1.3] Login con usuario inexistente...")
    res_bad_user = client.post("/login", data={"identificador": "noexiste@sistema.mx", "password": "Admin123"})
    assert res_bad_user.status_code == 401
    html_user = res_bad_user.data.decode("utf-8")
    assert "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa." in html_user
    print(" -> PASÓ: Mensaje de error genérico uniforme en ambos casos sin revelar datos.")

    # Criterio 3: Cuenta inactiva no entra
    from models.user import UserModel
    UserModel.create_user("inactivo", "inactivo@sistema.mx", "Inactivo123", "Inactivo Test", "Usuario", "Inactivo")
    client.get("/logout")
    print("[TEST 1.4] Login con cuenta inactiva (inactivo@sistema.mx)...")
    res_inactive = client.post("/login", data={"identificador": "inactivo@sistema.mx", "password": "Inactivo123"})
    assert res_inactive.status_code == 401
    html_inact = res_inactive.data.decode("utf-8")
    assert "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa." in html_inact
    print(" -> PASÓ: Cuenta inactiva es rechazada con el mismo mensaje genérico uniforme.")

    # Criterio 4: Cierre de sesión elimina acceso protegido
    print("[TEST 1.5] Verificando acceso protegido con sesión activa...")
    client.post("/login", data={"identificador": "admin@sistema.mx", "password": "Admin123"})
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200

    print("[TEST 1.6] Ejecutando cierre de sesión (/logout)...")
    res_logout = client.get("/logout", follow_redirects=False)
    assert res_logout.status_code == 302
    assert "notice=logged_out" in res_logout.headers.get("Location", "")

    print("[TEST 1.7] Verificando que la sesión cerrada ya NO permite acceso a páginas protegidas...")
    res_dash_blocked = client.get("/dashboard", follow_redirects=False)
    assert res_dash_blocked.status_code == 302
    assert "/login" in res_dash_blocked.headers.get("Location", "")

    res_login_page = client.get("/login?notice=logged_out")
    assert "Tu sesión ha finalizado correctamente." in res_login_page.data.decode("utf-8")
    print(" -> PASÓ: Cierre de sesión revoca inmediatamente el acceso y muestra banner verde de confirmación.")

    # Criterio 5: Autoservicio de registro y creación al intentar ingresar si el usuario no existe
    print("[TEST 1.8] Verificando que al ingresar con usuario inexistente se ofrece crearlo con rol Usuario...")
    client.get("/logout")
    res_no_existe = client.post("/login", data={"identificador": "nuevo_operador@bajio.mx", "password": "Operador123"})
    assert res_no_existe.status_code == 401
    html_ne = res_no_existe.data.decode("utf-8")
    assert "Acceso denegado. Las credenciales ingresadas no son válidas o la cuenta no se encuentra activa." in html_ne
    assert "nuevo_operador@bajio.mx" in html_ne
    assert "¿El usuario no existe? Créalo ahora mismo" in html_ne or "Crear Usuario y Acceder" in html_ne
    print(" -> PASÓ: Pantalla de login ofrece opción contextual para crear el usuario no existente.")

    print("[TEST 1.9] Registrando usuario inexistente y verificando asignación de rol Usuario por defecto...")
    res_reg = client.post("/register", data={
        "identificador": "nuevo_operador@bajio.mx",
        "password": "Operador123",
        "nombre_completo": "Juan Operador Nuevo"
    }, follow_redirects=False)
    assert res_reg.status_code == 302
    assert "/dashboard" in res_reg.headers.get("Location", "")

    # Validar en base de datos
    u_created = UserModel.get_by_identifier("nuevo_operador@bajio.mx")
    assert u_created is not None, "El usuario debió guardarse en base de datos"
    assert u_created["rol"] == "Usuario", f"El rol debió ser Usuario por defecto, obtenido: {u_created['rol']}"
    assert u_created["estado"] == "Activo"
    assert u_created["nombre_completo"] == "Juan Operador Nuevo"

    # Validar acceso autenticado directo
    res_dash_new = client.get("/dashboard")
    assert res_dash_new.status_code == 200
    assert "Juan Operador Nuevo" in res_dash_new.data.decode("utf-8")
    print(" -> PASÓ: Usuario creado automáticamente con rol Usuario por defecto y autenticado con éxito.")

    # Criterio 6: Validación estricta de correo (obligatorio @) y contraseña robusta (8 caracteres, números, mayúsculas y minúsculas)
    print("[TEST 1.10] Verificando validaciones estrictas de correo (con @) y contraseña (8 chars, num, mayús, minús)...")
    client.get("/logout")
    # 1. Correo sin @
    res_no_at = client.post("/register", data={
        "identificador": "correosinat.com",
        "password": "Password123",
        "nombre_completo": "Test Sin Arroba"
    })
    assert res_no_at.status_code == 400
    assert "@" in res_no_at.data.decode("utf-8")

    # 2. Contraseña menor a 8 caracteres
    res_short = client.post("/register", data={
        "identificador": "user_short@bajio.mx",
        "password": "P1a",
        "nombre_completo": "Test Corta"
    })
    assert res_short.status_code == 400
    assert "8 caracteres" in res_short.data.decode("utf-8")

    # 3. Contraseña sin números
    res_no_num = client.post("/register", data={
        "identificador": "user_nonum@bajio.mx",
        "password": "PasswordSoloLetras",
        "nombre_completo": "Test Sin Num"
    })
    assert res_no_num.status_code == 400
    assert "número" in res_no_num.data.decode("utf-8")

    # 4. Contraseña sin mayúsculas
    res_no_upper = client.post("/register", data={
        "identificador": "user_noupper@bajio.mx",
        "password": "password123",
        "nombre_completo": "Test Sin Mayus"
    })
    assert res_no_upper.status_code == 400
    assert "mayúscula" in res_no_upper.data.decode("utf-8")

    # 5. Contraseña sin minúsculas
    res_no_lower = client.post("/register", data={
        "identificador": "user_nolower@bajio.mx",
        "password": "PASSWORD123",
        "nombre_completo": "Test Sin Minus"
    })
    assert res_no_lower.status_code == 400
    assert "minúscula" in res_no_lower.data.decode("utf-8")
    print(" -> PASÓ: Todas las reglas de correo (@) y contraseña (8 chars, nums, mayús, minús) validadas estrictamente.")

    # Criterio 7: Recuperación de contraseña (/recuperar-password)
    print("[TEST 1.11] Verificando flujo de recuperación de contraseña (/recuperar-password)...")
    client.get("/logout")
    # 1. Recuperar con correo existente y nueva contraseña robusta
    res_recup = client.post("/recuperar-password", data={
        "identificador": "nuevo_operador@bajio.mx",
        "nueva_contrasena": "NuevaClave456",
        "confirm_password": "NuevaClave456"
    }, follow_redirects=False)
    assert res_recup.status_code == 302
    assert "notice=pwd_reset" in res_recup.headers.get("Location", "")

    # 2. Login con la nueva contraseña
    res_login_nueva = client.post("/login", data={
        "identificador": "nuevo_operador@bajio.mx",
        "password": "NuevaClave456"
    }, follow_redirects=False)
    assert res_login_nueva.status_code == 302
    assert "/dashboard" in res_login_nueva.headers.get("Location", "")
    print(" -> PASÓ: Contraseña restablecida exitosamente y verificada con inicio de sesión correcto.")

    print("="*70)
    print(" TODOS LOS CRITERIOS DE HISTORIA DE USUARIO 1 (FLASK) VERIFICADOS EXITOSAMENTE!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_historia_usuario_1()

