"""Test setup: every test gets a fresh, empty SQLite database (MySQL is never touched).

Run all tests from the project folder:   python -m pytest
"""
import os
import tempfile
from pathlib import Path

# Must be set before the app is imported, because app.config reads it at import time.
_TMP = Path(tempfile.mkdtemp(prefix="ecowaste-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role  # noqa: E402
from app.services import special_item_service  # noqa: E402
from app.services.auth_service import register_user  # noqa: E402

PASSWORD = "Secret123!"

DEFAULT_PROFILE = {
    Role.RESIDENT: {"address": "House 1, Road 2, Dhaka"},
    Role.RECYCLER: {"company_name": "Recycle Co"},
    Role.SPONSOR: {"organization_name": "Sponsor Org"},
}


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(special_item_service, "PHOTO_DIR", tmp_path / "photos")
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db):
    """make_user(Role.MANAGER) or make_user(Role.RESIDENT, email="x@test.com", address="...")"""
    counter = {"n": 0}

    def _make(role: Role, email: str | None = None, name: str | None = None, **profile):
        counter["n"] += 1
        email = email or f"{role.value}{counter['n']}@test.com"
        data = {**DEFAULT_PROFILE.get(role, {}), **profile}
        return register_user(db, role=role, name=name or f"{role.label} {counter['n']}", email=email,
                             password=PASSWORD, profile=data)

    return _make


def login(client: TestClient, email: str, password: str = PASSWORD):
    client.post("/logout")
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 200, response.text[:500]
    assert "Log out" in response.text
    return response


@pytest.fixture
def as_role(client, make_user):
    """as_role(Role.ADMINISTRATOR) -> creates that user and logs the test client in as them."""

    def _as(role: Role, **kwargs):
        user = make_user(role, **kwargs)
        login(client, user.email)
        return user

    return _as
