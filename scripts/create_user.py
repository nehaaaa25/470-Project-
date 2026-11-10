"""Create any type of account from the terminal (used for staff: Admin, Manager, Collector, Centre Staff).

Run from the project folder (with .venv active):
    python -m scripts.create_user
"""
import getpass
import sys

from app.database import SessionLocal
from app.models import Role
from app.services.auth_service import FIELD_LABELS, PROFILE_FIELDS, REQUIRED_FIELDS, RegistrationError, register_user


def main() -> int:
    roles = list(Role)
    print("Account type:")
    for i, r in enumerate(roles, 1):
        print(f"  {i}. {r.label}")
    choice = input("Number: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(roles):
        print("Invalid choice.")
        return 1
    role = roles[int(choice) - 1]

    name = input("Full name: ")
    email = input("Email: ")
    phone = input("Phone (optional): ")
    profile = {}
    for field in PROFILE_FIELDS[role]:
        optional = "" if field in REQUIRED_FIELDS.get(role, ()) else " (optional)"
        profile[field] = input(f"{FIELD_LABELS[field]}{optional}: ")
    password = getpass.getpass("Password (8-72 characters, hidden): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1

    with SessionLocal() as db:
        try:
            user = register_user(db, role=role, name=name, email=email, password=password, phone=phone, profile=profile)
        except RegistrationError as e:
            print(f"Error: {e}")
            return 1
    print(f"Created {user.role_label} account #{user.id} for {user.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
