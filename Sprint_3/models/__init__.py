# Modelos del Sistema organizados por Sprints
from models.sprint_1.user import UserModel
from models.sprint_2.equipment import EquipmentModel, AreaModel, CatalogModel
from models.sprint_3.ticket import TicketModel, MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS

__all__ = [
    "UserModel",
    "EquipmentModel",
    "AreaModel",
    "CatalogModel",
    "TicketModel",
    "MAX_CONTENT_LENGTH",
    "ALLOWED_EXTENSIONS"
]
