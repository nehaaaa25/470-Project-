"""MODEL layer. Import every model here so Alembic can see all tables.

When you add a new model file (e.g. booking.py), add one import line below.
"""
from app.database import Base
from app.models.user import (
    ROLE_MODELS,
    Administrator,
    CentreStaff,
    Collector,
    Manager,
    Recycler,
    Resident,
    Role,
    Sponsor,
    User,
)
from app.models.material import BinType, MaterialCategory, PreparationInstruction          # #4  Neha
from app.models.zone import ServiceZone, collector_zones                                   # #10 Esha
from app.models.centre import CollectionCentre, centre_materials                           # #14 Nowrin
from app.models.reward import Reward, RewardCommitment, RewardStatus                       # #20 Rifa
from app.models.special_item import (                                                      # #5  Neha
    ItemType,
    RequestStatus,
    SpecialistService,
    SpecialItemRequest,
)

__all__ = [
    "Base", "Role", "ROLE_MODELS", "User", "Resident", "Collector", "CentreStaff",
    "Recycler", "Sponsor", "Manager", "Administrator",
    "BinType", "MaterialCategory", "PreparationInstruction",
    "ServiceZone", "collector_zones",
    "CollectionCentre", "centre_materials",
    "Reward", "RewardCommitment", "RewardStatus",
    "ItemType", "RequestStatus", "SpecialistService", "SpecialItemRequest",
]
