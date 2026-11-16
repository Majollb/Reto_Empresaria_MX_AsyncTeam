import re
from database.db import get_db_connection
from auth.security import hash_password, revoke_all_user_sessions, validate_email_format, validate_password_policy, calculate_password_strength

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}$")

class UserModel:
    @staticmethod
    def get_by_id(user_id: int):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE id = ?;", (user_id,)).fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def get_by_identifier(identifier: str):
        """Busca un usuario por correo o nombre de usuario (sin distinción de mayúsculas)."""
        if not identifier:
            return None
        clean_ident = identifier.strip()
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE lower(username) = lower(?) OR lower(email) = lower(?);",
            (clean_ident, clean_ident)
        ).fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def get_all(search: str = None, role: str = None, status: str = None):
        """Retorna lista de usuarios con filtros opcionales."""
        conn = get_db_connection()
        query = "SELECT id, username, email, nombre_completo, rol, estado, created_at, updated_at FROM usuarios WHERE 1=1"
        params = []

        if search:
            query += " AND (nombre_completo LIKE ? OR username LIKE ? OR email LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        if role and role in ('Admin', 'Usuario', 'Responsable'):
            query += " AND rol = ?"
            params.append(role)

        if status and status in ('Activo', 'Inactivo'):
            query += " AND estado = ?"
            params.append(status)

        query += " ORDER BY id DESC;"
        users = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(u) for u in users]

    @staticmethod
    def exists_username(username: str, exclude_user_id: int = None) -> bool:
        conn = get_db_connection()
        if exclude_user_id:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE lower(username) = lower(?) AND id != ?;",
                (username.strip(), exclude_user_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE lower(username) = lower(?);",
                (username.strip(),)
            ).fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def exists_email(email: str, exclude_user_id: int = None) -> bool:
        conn = get_db_connection()
        if exclude_user_id:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE lower(email) = lower(?) AND id != ?;",
                (email.strip(), exclude_user_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE lower(email) = lower(?);",
                (email.strip(),)
            ).fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def create_user(username: str, email: str, password: str, nombre_completo: str, rol: str, estado: str = 'Activo') -> tuple[dict | None, str | None]:
        """Registra un nuevo usuario garantizando unicidad de identificadores y validaciones."""
        username = username.strip() if username else ""
        email = email.strip() if email else ""
        nombre_completo = nombre_completo.strip() if nombre_completo else ""

        # Validaciones de campos obligatorios
        if not username or not email or not password or not nombre_completo:
            return None, "Todos los campos marcados con asterisco (*) son obligatorios."

        if len(username) < 3:
            return None, "El nombre de usuario debe contener al menos 3 caracteres."

        if not EMAIL_REGEX.match(email):
            return None, "El formato de correo electrónico no es válido."

        if len(password) < 6:
            return None, "La contraseña debe tener una longitud mínima de 6 caracteres."

        if rol not in ('Admin', 'Usuario', 'Responsable'):
            return None, "El rol especificado no es válido."

        if estado not in ('Activo', 'Inactivo'):
            estado = 'Activo'

        # Control estricto de unicidad de identificadores (HU3)
        if UserModel.exists_username(username):
            return None, f"El identificador de usuario '{username}' ya está registrado en el sistema."

        if UserModel.exists_email(email):
            return None, f"El correo electrónico '{email}' ya se encuentra asignado a otra cuenta."

        pwd_hash, salt = hash_password(password)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (username, email, password_hash, salt, nombre_completo, rol, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (username, email, pwd_hash, salt, nombre_completo, rol, estado))
            conn.commit()
            new_id = cursor.lastrowid
            user = UserModel.get_by_id(new_id)
            return user, None
        except Exception as e:
            conn.rollback()
            return None, f"Error al crear el usuario en la base de datos: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def register_user(identificador: str, password: str, nombre_completo: str = "") -> tuple[dict | None, str | None]:
        """
        Registra un nuevo usuario por autoservicio desde la pantalla de login.
        Valida que el correo contenga estrictamente el carácter '@' y que la contraseña
        tenga al menos 8 caracteres con números, letras minúsculas y mayúsculas.
        Por defecto se crea estrictamente con el rol 'Usuario' y estado 'Activo'.
        """
        ident = (identificador or "").strip()
        pwd = password or ""
        
        # 1. Validación estricta del correo (debe tener sí o sí '@')
        is_email_valid, email_err = validate_email_format(ident)
        if not is_email_valid:
            # Si el usuario pasó un username sin arroba en el registro
            if "@" not in ident:
                return None, "El correo electrónico es obligatorio y debe contener el símbolo '@' (ejemplo: usuario@empresa.com)."
            return None, email_err

        # 2. Validación estricta de contraseña (8 caracteres, números, mayúsculas y minúsculas)
        is_pwd_valid, pwd_err = validate_password_policy(pwd)
        if not is_pwd_valid:
            return None, pwd_err

        email = ident.lower()
        base_user = email.split("@")[0]
        clean_user = re.sub(r'[^a-zA-Z0-9_]', '', base_user)
        if len(clean_user) < 3:
            clean_user = f"usr_{clean_user}"
        username = clean_user

        # Resolver colisiones en username derivado
        if UserModel.exists_username(username):
            import time
            username = f"{username}_{int(time.time()) % 1000}"

        if UserModel.exists_email(email):
            return None, f"El correo electrónico '{email}' ya se encuentra registrado. ¿Deseas iniciar sesión o recuperar tu contraseña?"

        nombre = (nombre_completo or "").strip()
        if not nombre:
            nombre = base_user.replace(".", " ").replace("_", " ").title()

        # Creación con rol Usuario por defecto
        return UserModel.create_user(
            username=username,
            email=email,
            password=pwd,
            nombre_completo=nombre,
            rol="Usuario",
            estado="Activo"
        )

    @staticmethod
    def reset_password(identificador_o_correo: str, nueva_contrasena: str) -> tuple[bool, str | None]:
        """
        Restablece la contraseña de una cuenta registrada validando la política de seguridad
        (mínimo 8 caracteres, números, letras mayúsculas y minúsculas).
        """
        ident = (identificador_o_correo or "").strip()
        if not ident:
            return False, "Debe ingresar su correo electrónico o identificador registrado."

        user = UserModel.get_by_identifier(ident)
        if not user:
            return False, f"No existe ninguna cuenta registrada con el identificador o correo '{ident}'."

        # Validar política de contraseña
        is_pwd_valid, pwd_err = validate_password_policy(nueva_contrasena)
        if not is_pwd_valid:
            return False, pwd_err

        # Hashing de nueva contraseña y regeneración de salteo criptográfico
        new_hash, new_salt = hash_password(nueva_contrasena)

        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE usuarios SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (new_hash, new_salt, user["id"])
            )
            conn.commit()
            # Invalidar sesiones existentes por seguridad
            revoke_all_user_sessions(user["id"])
            return True, None
        except Exception as e:
            conn.rollback()
            return False, f"Error al restablecer la contraseña en la base de datos: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def update_user(user_id: int, username: str, email: str, nombre_completo: str, rol: str, estado: str, new_password: str = None) -> tuple[dict | None, str | None]:
        """Actualiza un usuario existente con validación de identificadores duplicados."""
        existing = UserModel.get_by_id(user_id)
        if not existing:
            return None, "El usuario a actualizar no existe."

        username = username.strip() if username else ""
        email = email.strip() if email else ""
        nombre_completo = nombre_completo.strip() if nombre_completo else ""

        if not username or not email or not nombre_completo:
            return None, "El nombre completo, usuario y correo electrónico son obligatorios."

        if len(username) < 3:
            return None, "El nombre de usuario debe tener al menos 3 caracteres."

        if not EMAIL_REGEX.match(email):
            return None, "El formato del correo electrónico no es válido."

        if rol not in ('Admin', 'Usuario', 'Responsable'):
            return None, "El rol especificado no es válido."

        if estado not in ('Activo', 'Inactivo'):
            return None, "El estado especificado no es válido."

        # Control de duplicados excluyendo el usuario actual
        if UserModel.exists_username(username, exclude_user_id=user_id):
            return None, f"El nombre de usuario '{username}' ya está en uso por otra cuenta."

        if UserModel.exists_email(email, exclude_user_id=user_id):
            return None, f"El correo electrónico '{email}' ya está en uso por otra cuenta."

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if new_password and new_password.strip():
                if len(new_password) < 6:
                    conn.close()
                    return None, "La nueva contraseña debe tener al menos 6 caracteres."
                pwd_hash, salt = hash_password(new_password)
                cursor.execute("""
                    UPDATE usuarios
                    SET username = ?, email = ?, nombre_completo = ?, rol = ?, estado = ?,
                        password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (username, email, nombre_completo, rol, estado, pwd_hash, salt, user_id))
            else:
                cursor.execute("""
                    UPDATE usuarios
                    SET username = ?, email = ?, nombre_completo = ?, rol = ?, estado = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (username, email, nombre_completo, rol, estado, user_id))

            conn.commit()

            # Si la cuenta fue desactivada, revocar de inmediato cualquier sesión activa
            if estado == 'Inactivo':
                revoke_all_user_sessions(user_id)

            updated = UserModel.get_by_id(user_id)
            return updated, None
        except Exception as e:
            conn.rollback()
            return None, f"Error al actualizar usuario: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def toggle_status(user_id: int) -> tuple[str | None, str | None]:
        """Alterna el estado Activo/Inactivo de un usuario."""
        user = UserModel.get_by_id(user_id)
        if not user:
            return None, "Usuario no encontrado."

        new_status = 'Inactivo' if user['estado'] == 'Activo' else 'Activo'
        conn = get_db_connection()
        try:
            conn.execute("""
                UPDATE usuarios SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;
            """, (new_status, user_id))
            conn.commit()

            if new_status == 'Inactivo':
                revoke_all_user_sessions(user_id)

            return new_status, None
        except Exception as e:
            conn.rollback()
            return None, f"Error al cambiar estado: {str(e)}"
        finally:
            conn.close()

