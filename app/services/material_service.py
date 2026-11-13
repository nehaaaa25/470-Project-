"""Business rules for #4 Waste Sorting Guide & Material Catalogue."""
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import BinType, MaterialCategory, PreparationInstruction
from app.services import validation as v
from app.services.validation import ServiceError

# ---------- Bin types ----------


def list_bin_types(db: Session) -> list[BinType]:
    return list(db.scalars(select(BinType).order_by(BinType.name)))


def get_bin_type(db: Session, bin_id: int) -> BinType | None:
    return db.get(BinType, bin_id)


def save_bin_type(db: Session, bin_type: BinType | None, *, name: str, colour: str, description: str) -> BinType:
    name = v.text(name, "Name", max_len=60)
    colour = v.hex_colour(colour)
    description = v.text(description, "Description", required=False)

    clash = db.scalar(select(BinType).where(func.lower(BinType.name) == name.lower()))
    if clash and clash is not bin_type:
        raise ServiceError(f"A bin type called '{name}' already exists.")

    bin_type = bin_type or BinType()
    bin_type.name, bin_type.colour, bin_type.description = name, colour, description
    db.add(bin_type)
    _commit(db, f"A bin type called '{name}' already exists.")
    return bin_type


def delete_bin_type(db: Session, bin_type: BinType) -> None:
    if bin_type.categories:
        names = ", ".join(c.name for c in bin_type.categories)
        raise ServiceError(f"This bin is still used by: {names}. Move those materials to another bin first.")
    db.delete(bin_type)
    db.commit()


# ---------- Material categories ----------


def search_categories(db: Session, keyword: str = "", bin_type_id: int | None = None) -> list[MaterialCategory]:
    """MaterialCategory.search(keyword) from the class diagram: matches name, description,
    examples and the preparation steps."""
    stmt = (
        select(MaterialCategory)
        .options(selectinload(MaterialCategory.instructions), selectinload(MaterialCategory.bin_type))
        .order_by(MaterialCategory.name)
    )
    keyword = keyword.strip()
    if keyword:
        like = f"%{keyword}%"
        step_match = select(PreparationInstruction.category_id).where(PreparationInstruction.instruction.ilike(like))
        stmt = stmt.where(
            or_(
                MaterialCategory.name.ilike(like),
                MaterialCategory.description.ilike(like),
                MaterialCategory.examples.ilike(like),
                MaterialCategory.id.in_(step_match),
            )
        )
    if bin_type_id:
        stmt = stmt.where(MaterialCategory.bin_type_id == bin_type_id)
    return list(db.scalars(stmt))


def list_categories(db: Session) -> list[MaterialCategory]:
    return list(db.scalars(select(MaterialCategory).order_by(MaterialCategory.name)))


def get_category(db: Session, category_id: int) -> MaterialCategory | None:
    return db.get(MaterialCategory, category_id)


def save_category(
    db: Session,
    category: MaterialCategory | None,
    *,
    name: str,
    description: str,
    examples: str,
    is_recyclable: bool,
    points_per_kg: str,
    bin_type_id: str,
    steps: str = "",
    is_biodegradable: bool = False,
) -> MaterialCategory:
    """Create (category=None) or update a category.
    `steps` is only used when creating: one preparation step per line."""
    name = v.text(name, "Name", max_len=80)
    description = v.text(description, "Description", required=False, max_len=2000)
    examples = v.text(examples, "Examples", required=False)
    points = v.integer(points_per_kg, "Points per kg", min_value=0, max_value=10000)
    if not is_recyclable and points:
        raise ServiceError("Non-recyclable materials cannot earn points. Set points per kg to 0.")

    bin_id = v.integer(bin_type_id, "Bin type", required=False)
    if bin_id is not None and db.get(BinType, bin_id) is None:
        raise ServiceError("Please choose a valid bin type.")

    clash = db.scalar(select(MaterialCategory).where(func.lower(MaterialCategory.name) == name.lower()))
    if clash and clash is not category:
        raise ServiceError(f"A material called '{name}' already exists.")

    is_new = category is None
    category = category or MaterialCategory()
    category.name, category.description, category.examples = name, description, examples
    category.is_recyclable, category.points_per_kg, category.bin_type_id = is_recyclable, points, bin_id
    category.is_biodegradable = is_biodegradable
    if is_new:
        for line in steps.splitlines():
            line = line.strip()
            if line:
                _add_step(category, line)
    db.add(category)
    _commit(db, f"A material called '{name}' already exists.")
    return category


def delete_category(db: Session, category: MaterialCategory) -> None:
    db.delete(category)  # its preparation steps go with it (composition)
    db.commit()


# ---------- Preparation instructions (steps) ----------


def _add_step(category: MaterialCategory, text: str) -> PreparationInstruction:
    text = v.text(text, "Step", max_len=255)
    step = PreparationInstruction(step_no=len(category.instructions) + 1, instruction=text)
    category.instructions.append(step)
    return step


def add_step(db: Session, category: MaterialCategory, text: str) -> PreparationInstruction:
    step = _add_step(category, text)
    db.commit()
    return step


def update_step(db: Session, category: MaterialCategory, step_id: int, text: str) -> None:
    step = _find_step(category, step_id)
    step.instruction = v.text(text, "Step", max_len=255)
    db.commit()


def delete_step(db: Session, category: MaterialCategory, step_id: int) -> None:
    category.instructions.remove(_find_step(category, step_id))
    _renumber(category)
    db.commit()


def move_step(db: Session, category: MaterialCategory, step_id: int, direction: str) -> None:
    steps = category.instructions
    i = steps.index(_find_step(category, step_id))
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(steps):
        steps[i].step_no, steps[j].step_no = steps[j].step_no, steps[i].step_no
        db.flush()
        db.commit()
        db.refresh(category)


def _find_step(category: MaterialCategory, step_id: int) -> PreparationInstruction:
    for step in category.instructions:
        if step.id == step_id:
            return step
    raise ServiceError("That step does not exist.")


def _renumber(category: MaterialCategory) -> None:
    for i, step in enumerate(category.instructions, 1):
        step.step_no = i


def _commit(db: Session, duplicate_message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(duplicate_message) from None
