"""User hierarchy from the class diagram.

User is abstract; each role is a subclass with its own table
(SQLAlchemy "joined-table inheritance"):

    users           <- shared columns (name, email, password, role, ...)
    residents       <- extra Resident columns, id is also a FK to users.id
    collectors      <- ...and so on for every role
"""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(StrEnum):
    RESIDENT = "resident"
    COLLECTOR = "collector"
    CENTRE_STAFF = "centre_staff"
    RECYCLER = "recycler"
    SPONSOR = "sponsor"
    MANAGER = "manager"
    ADMINISTRATOR = "administrator"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    __mapper_args__ = {"polymorphic_on": "role", "polymorphic_abstract": True}

    @property
    def role_label(self) -> str:
        return Role(self.role).label

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id} email={self.email!r}>"


def _user_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Resident(User):
    __tablename__ = "residents"
    id: Mapped[int] = _user_fk()
    address: Mapped[str] = mapped_column(String(255))
    resident_type: Mapped[str] = mapped_column(String(20), default="household")  # household / business
    __mapper_args__ = {"polymorphic_identity": Role.RESIDENT.value}


class Collector(User):
    __tablename__ = "collectors"
    id: Mapped[int] = _user_fk()
    vehicle_no: Mapped[str | None] = mapped_column(String(30))
    availability_status: Mapped[str] = mapped_column(String(20), default="available")
    __mapper_args__ = {"polymorphic_identity": Role.COLLECTOR.value}


class CentreStaff(User):
    __tablename__ = "centre_staff"
    id: Mapped[int] = _user_fk()
    designation: Mapped[str | None] = mapped_column(String(60))
    __mapper_args__ = {"polymorphic_identity": Role.CENTRE_STAFF.value}


class Recycler(User):
    __tablename__ = "recyclers"
    id: Mapped[int] = _user_fk()
    company_name: Mapped[str] = mapped_column(String(150))
    trade_license_no: Mapped[str | None] = mapped_column(String(60))
    __mapper_args__ = {"polymorphic_identity": Role.RECYCLER.value}


class Sponsor(User):
    __tablename__ = "sponsors"
    id: Mapped[int] = _user_fk()
    organization_name: Mapped[str] = mapped_column(String(150))
    contact_person: Mapped[str | None] = mapped_column(String(100))
    __mapper_args__ = {"polymorphic_identity": Role.SPONSOR.value}


class Manager(User):
    __tablename__ = "managers"
    id: Mapped[int] = _user_fk()
    employee_code: Mapped[str | None] = mapped_column(String(30))
    __mapper_args__ = {"polymorphic_identity": Role.MANAGER.value}


class Administrator(User):
    __tablename__ = "administrators"
    id: Mapped[int] = _user_fk()
    admin_level: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"polymorphic_identity": Role.ADMINISTRATOR.value}


ROLE_MODELS: dict[Role, type[User]] = {
    Role.RESIDENT: Resident,
    Role.COLLECTOR: Collector,
    Role.CENTRE_STAFF: CentreStaff,
    Role.RECYCLER: Recycler,
    Role.SPONSOR: Sponsor,
    Role.MANAGER: Manager,
    Role.ADMINISTRATOR: Administrator,
}
