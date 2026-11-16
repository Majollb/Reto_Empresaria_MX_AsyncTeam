# Modelos del Sistema organizados por Sprints
from models.sprint_1.user import UserModel
from models.sprint_2.equipment import EquipmentModel, AreaModel, CatalogModel
from models.sprint_4.ticket import TicketModel, MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS
from models.sprint_4.reports import ReportsModel

__all__ = [
    "UserModel",
    "EquipmentModel",
    "AreaModel",
    "CatalogModel",
    "TicketModel",
    "ReportsModel",
    "MAX_CONTENT_LENGTH",
    "ALLOWED_EXTENSIONS"
]
