from auth.security import parse_and_validate_session, revoke_all_user_sessions
from models.user import UserModel
from models.ticket import TicketModel
from config import SESSION_COOKIE_NAME

def get_session_from_request(request) -> dict | None:
    """Extrae y valida la sesión desde la cookie de la solicitud."""
    cookie_header = request.headers.get("Cookie", "")
    if not cookie_header:
        return None
        
    cookies = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
            
    token = cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
        
    session_data = parse_and_validate_session(token)
    return session_data

def get_current_user(request) -> dict | None:
    """
    Obtiene el usuario actual autenticado.
    Verifica obligatoriamente que la cuenta esté activa (HU1 y HU3).
    Si la cuenta está inactiva, invalida sesiones y retorna None.
    """
    session_data = get_session_from_request(request)
    if not session_data:
        return None
        
    uid = session_data.get("uid")
    if not uid:
        return None
        
    user = UserModel.get_by_id(uid)
    if not user:
        return None
        
    # Criterio mínimo HU1 & HU3: Cuenta inactiva no entra ni mantiene sesión
    if user.get("estado") != "Activo":
        revoke_all_user_sessions(uid)
        return None
        
    return user

def can_access_ticket(user: dict, ticket: dict, action: str = "view") -> bool:
    """Verifica permisos de acceso directo a un ticket específico (HU2)."""
    if not user or not ticket:
        return False
        
    if action == "view":
        return TicketModel.user_can_view(user, ticket)
    elif action == "modify":
        return TicketModel.user_can_modify(user, ticket)
        
    return False

