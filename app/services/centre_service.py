"""Business rules for #14 Collection Centre Management."""
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import CollectionCentre, MaterialCategory, centre_materials
from app.services import validation as v
from app.services.validation import ServiceError


def search_centres(
    db: Session, *, keyword: str = "", material_id: int | None = None, include_inactive: bool = False,
) -> list[CollectionCentre]:
    stmt = select(CollectionCentre).options(selectinload(CollectionCentre.materials)).order_by(CollectionCentre.name)
    if not include_inactive:
        stmt = stmt.where(CollectionCentre.is_active.is_(True))
    keyword = keyword.strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(CollectionCentre.name.ilike(like), CollectionCentre.address.ilike(like)))
    if material_id:
        accepts = select(centre_materials.c.centre_id).where(centre_materials.c.material_category_id == material_id)
        stmt = stmt.where(CollectionCentre.id.in_(accepts))
    return list(db.scalars(stmt))


def get_centre(db: Session, centre_id: int) -> CollectionCentre | None:
    return db.get(CollectionCentre, centre_id)


def save_centre(
    db: Session,
    centre: CollectionCentre | None,
    *,
    name: str,
    address: str,
    phone: str,
    opening_hours: str,
    processing_capacity_kg: str,
    latitude: str,
    longitude: str,
    is_active: bool,
    material_ids: list[int],
) -> CollectionCentre:
    name = v.text(name, "Centre name", max_len=120)
    address = v.text(address, "Address")
    phone = v.text(phone, "Phone", required=False, max_len=20)
    hours = v.text(opening_hours, "Opening hours", max_len=120)
    capacity = v.number(processing_capacity_kg, "Processing capacity (kg/day)", min_value=0, exclusive_min=True,
                        max_value=10_000_000)
    lat = v.number(latitude, "Latitude", required=False, min_value=-90, max_value=90)
    lng = v.number(longitude, "Longitude", required=False, min_value=-180, max_value=180)
    if (lat is None) != (lng is None):
        raise ServiceError("Enter both latitude and longitude, or leave both empty.")

    ids = set(material_ids or [])
    if not ids:
        raise ServiceError("Choose at least one accepted material.")
    materials = list(db.scalars(select(MaterialCategory).where(MaterialCategory.id.in_(ids))))
    if len(materials) != len(ids):
        raise ServiceError("One of the chosen materials does not exist.")

    clash = db.scalar(select(CollectionCentre).where(func.lower(CollectionCentre.name) == name.lower()))
    if clash and clash is not centre:
        raise ServiceError(f"A centre called '{name}' already exists.")

    centre = centre or CollectionCentre()
    centre.name, centre.address, centre.phone, centre.opening_hours = name, address, phone, hours
    centre.processing_capacity_kg, centre.latitude, centre.longitude = capacity, lat, lng
    centre.is_active = is_active
    centre.materials = materials
    db.add(centre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(f"A centre called '{name}' already exists.") from None
    return centre


def delete_centre(db: Session, centre: CollectionCentre) -> None:
    db.delete(centre)
    db.commit()
