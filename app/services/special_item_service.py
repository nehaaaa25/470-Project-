"""Business rules for #5 Special Item Collection Requests.

Rules:
- Only residents submit requests; a resident sees only their own requests.
- Managers and administrators review pending requests.
- Approving a request needs an *active* specialist service that handles that item type
  (ordinary collectors are never assigned special waste).
- Rejecting a request needs a reason, so the resident knows why.
- Only pending requests can be reviewed or cancelled.
"""
import secrets

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import UPLOAD_DIR
from app.models import ItemType, RequestStatus, Resident, Role, SpecialistService, SpecialItemRequest, User
from app.services import validation as v
from app.services.validation import ServiceError

REVIEWER_ROLES = (Role.MANAGER, Role.ADMINISTRATOR)
PHOTO_DIR = UPLOAD_DIR / "special_items"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
# File signatures ("magic bytes"), so a renamed .exe cannot pose as a photo.
PHOTO_SIGNATURES = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}


def is_reviewer(user: User) -> bool:
    return user.role in {r.value for r in REVIEWER_ROLES}


def can_view(user: User, request: SpecialItemRequest) -> bool:
    return is_reviewer(user) or request.resident_id == user.id


# ---------- Requests ----------


def list_requests(db: Session, *, resident: Resident | None = None, status: str = "") -> list[SpecialItemRequest]:
    stmt = (
        select(SpecialItemRequest)
        .options(selectinload(SpecialItemRequest.resident), selectinload(SpecialItemRequest.specialist_service))
        .order_by(SpecialItemRequest.submitted_at.desc(), SpecialItemRequest.id.desc())
    )
    if resident is not None:
        stmt = stmt.where(SpecialItemRequest.resident_id == resident.id)
    if status:
        stmt = stmt.where(SpecialItemRequest.status == status)
    return list(db.scalars(stmt))


def count_by_status(db: Session, resident: Resident | None = None) -> dict[str, int]:
    stmt = select(SpecialItemRequest.status, func.count()).group_by(SpecialItemRequest.status)
    if resident is not None:
        stmt = stmt.where(SpecialItemRequest.resident_id == resident.id)
    counts = {s.value: 0 for s in RequestStatus}
    counts.update({status: n for status, n in db.execute(stmt)})
    return counts


def get_request(db: Session, request_id: int) -> SpecialItemRequest | None:
    return db.get(SpecialItemRequest, request_id)


def submit_request(
    db: Session, resident: Resident, *, item_type: str, description: str, pickup_address: str,
    photo: UploadFile | None = None,
) -> SpecialItemRequest:
    item_type = v.choice(item_type, "Item type", list(ItemType))
    description = v.text(description, "Description", max_len=2000)
    address = v.text(pickup_address, "Pickup address")
    photo_name = _save_photo(photo) if photo is not None and photo.filename else None

    request = SpecialItemRequest(
        resident_id=resident.id, item_type=item_type, description=description,
        pickup_address=address, photo_path=photo_name, status=RequestStatus.PENDING.value,
    )
    db.add(request)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _delete_photo(photo_name)
        raise
    return request


def approve(db: Session, request: SpecialItemRequest, reviewer: User, *, service_id: str, note: str) -> None:
    _check_reviewable(request, reviewer)
    sid = v.integer(service_id, "Specialist service")
    service = db.get(SpecialistService, sid)
    if service is None or not service.is_active:
        raise ServiceError("Please choose an active specialist service.")
    if service.service_type != request.item_type:
        raise ServiceError(
            f"{service.name} handles {service.type_label.lower()}, not {request.type_label.lower()}."
        )
    request.approve(v.text(note, "Note", required=False, max_len=2000), service, reviewer)
    db.commit()


def reject(db: Session, request: SpecialItemRequest, reviewer: User, *, note: str) -> None:
    _check_reviewable(request, reviewer)
    request.reject(v.text(note, "Reason for rejection", max_len=2000), reviewer)
    db.commit()


def cancel(db: Session, request: SpecialItemRequest, user: User) -> None:
    if request.resident_id != user.id:
        raise ServiceError("You can only cancel your own requests.")
    if not request.is_pending:
        raise ServiceError("Only pending requests can be cancelled.")
    request.status = RequestStatus.CANCELLED.value
    db.commit()


def _check_reviewable(request: SpecialItemRequest, reviewer: User) -> None:
    if not is_reviewer(reviewer):
        raise ServiceError("Only managers and administrators can review requests.")
    if not request.is_pending:
        raise ServiceError(f"This request is already {request.status}.")


# ---------- Photos ----------


def photo_file(request: SpecialItemRequest):
    if not request.photo_path:
        return None
    path = PHOTO_DIR / request.photo_path
    return path if path.is_file() else None


def _save_photo(photo: UploadFile) -> str:
    data = photo.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise ServiceError("The photo must be 5 MB or smaller.")
    ext = next((e for sig, e in PHOTO_SIGNATURES.items() if data.startswith(sig)), None)
    if ext is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    if ext is None:
        raise ServiceError("The photo must be a JPG, PNG or WEBP image.")
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(16) + ext  # random name: never trust the uploaded file name
    (PHOTO_DIR / name).write_bytes(data)
    return name


def _delete_photo(name: str | None) -> None:
    if name:
        (PHOTO_DIR / name).unlink(missing_ok=True)


# ---------- Specialist services ----------


def list_services(db: Session, *, item_type: str | None = None, active_only: bool = False) -> list[SpecialistService]:
    stmt = select(SpecialistService).order_by(SpecialistService.service_type, SpecialistService.name)
    if item_type:
        stmt = stmt.where(SpecialistService.service_type == item_type)
    if active_only:
        stmt = stmt.where(SpecialistService.is_active.is_(True))
    return list(db.scalars(stmt))


def get_service(db: Session, service_id: int) -> SpecialistService | None:
    return db.get(SpecialistService, service_id)


def save_service(
    db: Session, service: SpecialistService | None, *, name: str, service_type: str, contact_phone: str,
    email: str, notes: str, is_active: bool,
) -> SpecialistService:
    name = v.text(name, "Service name", max_len=120)
    service_type = v.choice(service_type, "Service type", list(ItemType))
    phone = v.text(contact_phone, "Contact phone", max_len=20)
    email = v.text(email, "Email", required=False)
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise ServiceError("Please enter a valid email address.")
    notes = v.text(notes, "Notes", required=False)

    clash = db.scalar(select(SpecialistService).where(func.lower(SpecialistService.name) == name.lower()))
    if clash and clash is not service:
        raise ServiceError(f"A service called '{name}' already exists.")

    service = service or SpecialistService()
    service.name, service.service_type, service.contact_phone = name, service_type, phone
    service.email, service.notes, service.is_active = email, notes, is_active
    db.add(service)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(f"A service called '{name}' already exists.") from None
    return service


def delete_service(db: Session, service: SpecialistService) -> None:
    if service.requests:
        raise ServiceError(
            "This service has requests referred to it, so it cannot be deleted. Untick 'Active' instead."
        )
    db.delete(service)
    db.commit()
