"""Feature #10: Collector & Service Zone Management (owner: Esha)

Class diagram:
    Collector * ---- * ServiceZone      (link table: collector_zones)
"""
from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import Collector

collector_zones = Table(
    "collector_zones",
    Base.metadata,
    Column("collector_id", ForeignKey("collectors.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", ForeignKey("service_zones.id", ondelete="CASCADE"), primary_key=True),
)


class ServiceZone(Base):
    __tablename__ = "service_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    area_description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    collectors: Mapped[list[Collector]] = relationship(
        secondary=collector_zones, back_populates="zones", order_by=Collector.id
    )

    def assign_collector(self, collector: Collector) -> None:
        if collector not in self.collectors:
            self.collectors.append(collector)

    def remove_collector(self, collector: Collector) -> None:
        if collector in self.collectors:
            self.collectors.remove(collector)

    def __repr__(self) -> str:
        return f"<ServiceZone {self.name!r}>"


# The other side of the M:N link, added here so user.py does not import feature models.
Collector.zones = relationship(
    ServiceZone, secondary=collector_zones, back_populates="collectors", order_by=ServiceZone.name
)
