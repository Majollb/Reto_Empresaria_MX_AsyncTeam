import os
from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent

# Configuración de base de datos
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_PATH = BASE_DIR / "database" / "tickets.db"

# Directorio de subida de archivos adjuntos (HU-05)
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Límite máximo de tamaño de archivo: 10 MB exactos (HU-05)
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB = 10,485,760 bytes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'docx', 'xlsx', 'zip'}

# Clave secreta para firma criptográfica de sesiones (HMAC)
SECRET_KEY = os.environ.get("APP_SECRET_KEY", "bajio_security_secret_key_2026_super_secure")

# Nombre de la cookie de sesión
SESSION_COOKIE_NAME = "bajio_session"

# Duración de la sesión en segundos (8 horas)
SESSION_MAX_AGE = 8 * 3600

# Puerto del servidor web
SERVER_PORT = int(os.environ.get("PORT", 5000))
SERVER_HOST = os.environ.get("HOST", "127.0.0.1")

# Datos corporativos
COMPANY_NAME = "AUTOMATIZACIÓN Y SOFTWARE DEL BAJÍO"
SYSTEM_NAME = "Sistema de Tickets de Mantenimiento"
TIMEZONE_LABEL = "América/Ciudad_de_México (CST)"
