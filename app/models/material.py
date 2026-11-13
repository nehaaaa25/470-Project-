"""Feature #4: Waste Sorting Guide & Material Catalogue (owner: Neha)

Class diagram:
    BinType 1 ---- * MaterialCategory 1 ◆---- * PreparationInstruction
"""
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BinType(Base):
    __tablename__ = "bin_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    colour: Mapped[str] = mapped_column(String(7), default="#6c757d")  # hex, e.g. #2e7d4f
    description: Mapped[str | None] = mapped_column(String(255))

    categories: Mapped[list["MaterialCategory"]] = relationship(back_populates="bin_type")

    def __repr__(self) -> str:
        return f"<BinType {self.name!r}>"


class MaterialCategory(Base):
    __tablename__ = "material_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[str | None] = mapped_column(String(255))  # e.g. "newspaper, cereal boxes"
    is_recyclable: Mapped[bool] = mapped_column(Boolean, default=True)
    # Breaks down naturally (food, paper, leaves). Set by the admin; the AI scanner shows it.
    is_biodegradable: Mapped[bool] = mapped_column(Boolean, default=False)
    points_per_kg: Mapped[int] = mapped_column(Integer, default=0)
    bin_type_id: Mapped[int | None] = mapped_column(ForeignKey("bin_types.id", ondelete="SET NULL"))

    bin_type: Mapped[BinType | None] = relationship(back_populates="categories")
    # Composition: instructions belong to the category and are deleted with it.
    instructions: Mapped[list["PreparationInstruction"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="PreparationInstruction.step_no",
    )

    def get_instructions(self) -> list["PreparationInstruction"]:
        return list(self.instructions)

    def __repr__(self) -> str:
        return f"<MaterialCategory {self.name!r}>"


class PreparationInstruction(Base):
    __tablename__ = "preparation_instructions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("material_categories.id", ondelete="CASCADE"), index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    instruction: Mapped[str] = mapped_column(String(255))

    category: Mapped[MaterialCategory] = relationship(back_populates="instructions")
