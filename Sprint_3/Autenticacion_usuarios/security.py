import os
import hmac
import hashlib
import json
import base64
import time
import secrets
from config import SECRET_KEY, SESSION_MAX_AGE

# Registro de sesiones activas en memoria para invalidación inmediata (logout o desactivación)
# key: session_id, value: dict(user_id, created_at, last_seen)
ACTIVE_SESSIONS = {}

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Genera hash seguro de contraseña usando PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return hashed.hex(), salt

def verify_password(password: str, hashed_hex: str, salt: str) -> bool:
    """Verifica la contraseña contra el hash almacenado usando tiempo constante."""
    try:
        new_hash, _ = hash_password(password, salt)
        return secrets.compare_digest(new_hash, hashed_hex)
    except Exception:
        return False

def create_session(user_id: int, role: str) -> str:
    """Crea una sesión segura y retorna un token firmado criptográficamente."""
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())
    
    payload = {
        "sid": session_id,
        "uid": user_id,
        "role": role,
        "iat": now,
        "exp": now + SESSION_MAX_AGE
    }
    
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    token = f"{payload_b64}.{signature}"
    
    # Registrar en memoria
    ACTIVE_SESSIONS[session_id] = {
        "user_id": user_id,
        "role": role,
        "created_at": now,
        "last_seen": now
    }
    
    return token

def parse_and_validate_session(token: str) -> dict | None:
    """Valida la firma y expiración del token de sesión. Verifica que siga activa en el registro."""
    if not token or "." not in token:
        return None
    
    try:
        payload_b64, signature = token.split(".", 1)
        expected_sig = hmac.new(
            SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not secrets.compare_digest(signature, expected_sig):
            return None
        
        # Padding si es necesario
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
            
        payload_json = base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        sid = payload.get("sid")
        if not sid or sid not in ACTIVE_SESSIONS:
            return None
        
        now = int(time.time())
        if payload.get("exp", 0) < now:
            # Sesión expirada
            revoke_session(sid)
            return None
            
        # Actualizar last_seen
        ACTIVE_SESSIONS[sid]["last_seen"] = now
        return payload
    except Exception:
        return None

def revoke_session(session_id: str) -> None:
    """Elimina una sesión activa (Logout)."""
    ACTIVE_SESSIONS.pop(session_id, None)

def revoke_all_user_sessions(user_id: int) -> None:
    """Revoca todas las sesiones activas de un usuario (cuando se desactiva su cuenta)."""
    to_delete = [sid for sid, data in ACTIVE_SESSIONS.items() if data.get("user_id") == user_id]
    for sid in to_delete:
        ACTIVE_SESSIONS.pop(sid, None)

import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate_email_format(email: str) -> tuple[bool, str | None]:
    """Valida estrictamente que el correo electrónico contenga el símbolo '@' y tenga un formato válido."""
    if not email or "@" not in email:
        return False, "El correo electrónico es obligatorio y debe contener el símbolo '@' (ejemplo: usuario@dominio.com)."
    clean = email.strip()
    if not EMAIL_REGEX.match(clean):
        return False, "El formato del correo electrónico no es válido. Debe contener '@' y un dominio válido (ej: usuario@bajio.mx)."
    return True, None

def validate_password_policy(password: str) -> tuple[bool, str | None]:
    """
    Valida la política de contraseñas de seguridad:
    - Longitud mínima de 8 caracteres.
    - Debe incluir al menos una letra minúscula.
    - Debe incluir al menos una letra mayúscula.
    - Debe incluir al menos un número (0-9).
    """
    if not password:
        return False, "La contraseña es obligatoria."
    if len(password) < 8:
        return False, f"La contraseña debe contener al menos 8 caracteres (actualmente tiene {len(password)})."
    if not re.search(r"[a-z]", password):
        return False, "La contraseña debe incluir al menos una letra minúscula (a-z)."
    if not re.search(r"[A-Z]", password):
        return False, "La contraseña debe incluir al menos una letra mayúscula (A-Z)."
    if not re.search(r"[0-9]", password):
        return False, "La contraseña debe incluir al menos un número (0-9)."
    return True, None

def calculate_password_strength(password: str) -> dict:
    """Calcula el nivel de seguridad de la contraseña: débil, buena, excelente."""
    if not password:
        return {"score": 0, "label": "Vacía", "class": "vacia", "percent": 0, "color": "#cbd5e1"}

    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[^a-zA-Z0-9]", password):
        score += 1

    has_basics = (
        len(password) >= 8 and
        bool(re.search(r"[0-9]", password)) and
        bool(re.search(r"[a-z]", password)) and
        bool(re.search(r"[A-Z]", password))
    )

    if not has_basics or score <= 3:
        return {"score": 1, "label": "Débil", "class": "debil", "percent": 33, "color": "#ef4444"}
    elif score == 4:
        return {"score": 2, "label": "Buena", "class": "buena", "percent": 66, "color": "#f59e0b"}
    else:
        return {"score": 3, "label": "Excelente", "class": "excelente", "percent": 100, "color": "#10b981"}

