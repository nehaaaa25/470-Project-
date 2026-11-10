"""Feature #14: Collection Centre Management (owner: Nowrin)

Class diagram:
    CollectionCentre * ---- * MaterialCategory   ("accepts", link table: centre_materials)
"""
from sqlalchemy import Boolean, Column, Double, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.material import MaterialCategory

centre_materials = Table(
    "centre_materials",
    Base.metadata,
    Column("centre_id", ForeignKey("collection_centres.id", ondelete="CASCADE"), primary_key=True),
    Column("material_category_id", ForeignKey("material_categories.id", ondelete="CASCADE"), primary_key=True),
)


class CollectionCentre(Base):
    __tablename__ = "collection_centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    address: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    opening_hours: Mapped[str] = mapped_column(String(120))  # e.g. "Sat-Thu 9:00-17:00"
    processing_capacity_kg: Mapped[float] = mapped_column(Double)  # per day
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    materials: Mapped[list[MaterialCategory]] = relationship(
        secondary=centre_materials, order_by=MaterialCategory.name
    )

    def accepts_material(self, material: MaterialCategory) -> bool:
        return material in self.materials

    def __repr__(self) -> str:
        return f"<CollectionCentre {self.name!r}>"
