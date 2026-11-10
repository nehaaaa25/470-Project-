"""Business rules for #10 Collector & Service Zone Management."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Collector, Role, ServiceZone
from app.services import auth_service
from app.services import validation as v
from app.services.validation import ServiceError

AVAILABILITY = ("available", "busy", "on_leave")


# ---------- Zones ----------


def list_zones(db: Session) -> list[ServiceZone]:
    return list(db.scalars(select(ServiceZone).options(selectinload(ServiceZone.collectors)).order_by(ServiceZone.name)))


def get_zone(db: Session, zone_id: int) -> ServiceZone | None:
    return db.get(ServiceZone, zone_id)


def save_zone(
    db: Session, zone: ServiceZone | None, *, name: str, area_description: str,
    is_active: bool, collector_ids: list[int],
) -> ServiceZone:
    name = v.text(name, "Zone name", max_len=80)
    area = v.text(area_description, "Area description", required=False)

    clash = db.scalar(select(ServiceZone).where(func.lower(ServiceZone.name) == name.lower()))
    if clash and clash is not zone:
        raise ServiceError(f"A zone called '{name}' already exists.")

    collectors = _load_collectors(db, collector_ids)
    zone = zone or ServiceZone()
    zone.name, zone.area_description, zone.is_active = name, area, is_active
    zone.collectors = collectors
    db.add(zone)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(f"A zone called '{name}' already exists.") from None
    return zone


def delete_zone(db: Session, zone: ServiceZone) -> None:
    db.delete(zone)  # link rows in collector_zones are removed too
    db.commit()


# ---------- Collectors ----------


def list_collectors(db: Session) -> list[Collector]:
    return list(db.scalars(select(Collector).options(selectinload(Collector.zones)).order_by(Collector.name)))


def get_collector(db: Session, collector_id: int) -> Collector | None:
    return db.get(Collector, collector_id)


def register_collector(
    db: Session, *, name: str, email: str, phone: str, vehicle_no: str, password: str,
    confirm_password: str, zone_ids: list[int],
) -> Collector:
    """Administrators register collectors (staff accounts cannot self-register)."""
    if password != confirm_password:
        raise ServiceError("The two passwords do not match.")
    zones = _load_zones(db, zone_ids)
    collector = auth_service.register_user(
        db, role=Role.COLLECTOR, name=name, email=email, password=password, phone=phone,
        profile={"vehicle_no": vehicle_no},
    )
    if zones:
        collector.zones = zones
        db.commit()
    return collector


def update_collector(
    db: Session, collector: Collector, *, name: str, phone: str, vehicle_no: str,
    availability_status: str, is_active: bool, zone_ids: list[int],
) -> Collector:
    collector.name = v.text(name, "Name", max_len=100)
    collector.phone = v.text(phone, "Phone", required=False, max_len=20)
    collector.vehicle_no = v.text(vehicle_no, "Vehicle number", required=False, max_len=30)
    collector.availability_status = v.choice(availability_status, "Availability", AVAILABILITY)
    collector.is_active = is_active
    collector.zones = _load_zones(db, zone_ids)
    db.commit()
    return collector


# ---------- helpers ----------


def _load_zones(db: Session, ids: list[int]) -> list[ServiceZone]:
    ids = set(ids or [])
    zones = list(db.scalars(select(ServiceZone).where(ServiceZone.id.in_(ids)))) if ids else []
    if len(zones) != len(ids):
        raise ServiceError("One of the chosen zones does not exist.")
    return zones


def _load_collectors(db: Session, ids: list[int]) -> list[Collector]:
    ids = set(ids or [])
    collectors = list(db.scalars(select(Collector).where(Collector.id.in_(ids)))) if ids else []
    if len(collectors) != len(ids):
        raise ServiceError("One of the chosen collectors does not exist.")
    return collectors
