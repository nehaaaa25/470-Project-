"""Feature #5: Special Item Collection Requests (owner: Neha)

Class diagram:
    Resident 1 ---- * SpecialItemRequest * ---- 0..1 SpecialistService

Status flow:   pending --approve()--> approved (referred to a specialist service)
               pending --reject()---> rejected
               pending --cancel()---> cancelled   (by the resident)
"""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import Resident, User


class ItemType(StrEnum):
    BULKY = "bulky"
    ELECTRONIC = "electronic"
    HAZARDOUS = "hazardous"

    @property
    def label(self) -> str:
        return {"bulky": "Bulky item", "electronic": "Electronic waste", "hazardous": "Hazardous waste"}[self.value]


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class SpecialistService(Base):
    __tablename__ = "specialist_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    service_type: Mapped[str] = mapped_column(String(20), index=True)  # an ItemType value
    contact_phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    requests: Mapped[list["SpecialItemRequest"]] = relationship(back_populates="specialist_service")

    @property
    def type_label(self) -> str:
        return ItemType(self.service_type).label


class SpecialItemRequest(Base):
    __tablename__ = "special_item_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    pickup_address: Mapped[str] = mapped_column(String(255))
    photo_path: Mapped[str | None] = mapped_column(String(255))  # file name inside uploads/special_items/
    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.PENDING.value, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    specialist_service_id: Mapped[int | None] = mapped_column(
        ForeignKey("specialist_services.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    resident: Mapped[Resident] = relationship(foreign_keys=[resident_id])
    specialist_service: Mapped[SpecialistService | None] = relationship(back_populates="requests")
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])

    @property
    def type_label(self) -> str:
        return ItemType(self.item_type).label

    @property
    def is_pending(self) -> bool:
        return self.status == RequestStatus.PENDING

    # Methods from the class diagram. The service layer checks the rules before calling them.
    def approve(self, note: str | None, service: SpecialistService, reviewer: User) -> None:
        self.refer_to(service)
        self._close(RequestStatus.APPROVED, note, reviewer)

    def reject(self, note: str, reviewer: User) -> None:
        self._close(RequestStatus.REJECTED, note, reviewer)

    def refer_to(self, service: SpecialistService) -> None:
        self.specialist_service = service

    def _close(self, status: RequestStatus, note: str | None, reviewer: User) -> None:
        self.status = status.value
        self.review_note = note
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.now()
