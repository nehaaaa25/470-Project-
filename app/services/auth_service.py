"""Business rules for accounts: password hashing, login check, registration."""
import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ROLE_MODELS, Role, User
from app.services.validation import ServiceError

# Roles a visitor may pick on the public Register page.
# Staff roles (collector, centre staff, manager, admin) are created with: python -m scripts.create_user
SELF_REGISTER_ROLES = (Role.RESIDENT, Role.RECYCLER, Role.SPONSOR)

# Extra form fields each role has (matches the subclass attributes in the class diagram).
PROFILE_FIELDS: dict[Role, tuple[str, ...]] = {
    Role.RESIDENT: ("address", "resident_type"),
    Role.COLLECTOR: ("vehicle_no",),
    Role.CENTRE_STAFF: ("designation",),
    Role.RECYCLER: ("company_name", "trade_license_no"),
    Role.SPONSOR: ("organization_name", "contact_person"),
    Role.MANAGER: ("employee_code",),
    Role.ADMINISTRATOR: ("admin_level",),
}
REQUIRED_FIELDS: dict[Role, tuple[str, ...]] = {
    Role.RESIDENT: ("address",),
    Role.RECYCLER: ("company_name",),
    Role.SPONSOR: ("organization_name",),
}
FIELD_LABELS = {
    "address": "Address",
    "resident_type": "Resident type",
    "vehicle_no": "Vehicle number",
    "designation": "Designation",
    "company_name": "Company name",
    "trade_license_no": "Trade licence number",
    "organization_name": "Organisation name",
    "contact_person": "Contact person",
    "employee_code": "Employee code",
    "admin_level": "Admin level",
}
RESIDENT_TYPES = ("household", "business")


class RegistrationError(ServiceError):
    """Raised with a user-friendly message when registration input is invalid."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # malformed hash or password longer than 72 bytes
        return False


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if email + password are right and the account is active."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def register_user(
    db: Session,
    *,
    role: str,
    name: str,
    email: str,
    password: str,
    phone: str = "",
    profile: dict[str, str] | None = None,
) -> User:
    try:
        role = Role(role)
    except ValueError:
        raise RegistrationError("Please choose a valid account type.") from None

    name, email, phone = name.strip(), normalize_email(email), phone.strip()
    if not name:
        raise RegistrationError("Name is required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise RegistrationError("Please enter a valid email address.")
    if not 8 <= len(password.encode()) <= 72:
        raise RegistrationError("Password must be 8 to 72 characters long.")
    if get_user_by_email(db, email):
        raise RegistrationError("An account with this email already exists.")

    # Keep only this role's fields, drop blanks so column defaults apply.
    extra = {k: str(v).strip() for k, v in (profile or {}).items() if k in PROFILE_FIELDS[role]}
    extra = {k: v for k, v in extra.items() if v}
    for field in REQUIRED_FIELDS.get(role, ()):
        if field not in extra:
            raise RegistrationError(f"{FIELD_LABELS[field]} is required.")
    if "resident_type" in extra and extra["resident_type"] not in RESIDENT_TYPES:
        raise RegistrationError("Resident type must be household or business.")
    if "admin_level" in extra:
        if not extra["admin_level"].isdigit():
            raise RegistrationError("Admin level must be a number.")
        extra["admin_level"] = int(extra["admin_level"])

    model = ROLE_MODELS[role]
    user = model(name=name, email=email, phone=phone or None, password_hash=hash_password(password), **extra)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RegistrationError("An account with this email already exists.") from None
    db.refresh(user)
    return user
