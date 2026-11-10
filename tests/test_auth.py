"""Login, logout, registration and access control."""
from sqlalchemy import select

from app.models import Resident, Role, User
from tests.conftest import PASSWORD, login


def test_register_login_logout(client, db):
    r = client.post("/register", data={
        "role": "resident", "name": "Neha", "email": "Neha@Test.com", "password": PASSWORD,
        "confirm_password": PASSWORD, "address": "Mohakhali", "resident_type": "household",
    })
    assert r.status_code == 200 and "Account created" in r.text

    user = db.scalar(select(User).where(User.email == "neha@test.com"))
    assert isinstance(user, Resident) and user.password_hash != PASSWORD

    r = login(client, "neha@test.com")
    assert "Hi, Neha" in r.text

    r = client.post("/logout")
    assert "You have been logged out" in r.text
    assert client.get("/dashboard", follow_redirects=False).status_code == 303


def test_wrong_password_and_inactive_account(client, make_user, db):
    user = make_user(Role.RESIDENT)
    r = client.post("/login", data={"email": user.email, "password": "wrong-pass"})
    assert r.status_code == 400 and "Wrong email or password" in r.text

    user.is_active = False
    db.commit()
    r = client.post("/login", data={"email": user.email, "password": PASSWORD})
    assert r.status_code == 400


def test_cannot_self_register_as_staff(client):
    r = client.post("/register", data={
        "role": "administrator", "name": "X", "email": "x@test.com", "password": PASSWORD,
        "confirm_password": PASSWORD,
    })
    assert r.status_code == 400 and "valid account type" in r.text


def test_register_validation(client, make_user):
    existing = make_user(Role.RESIDENT)
    base = {"role": "resident", "name": "A", "email": "a@test.com", "password": PASSWORD,
            "confirm_password": PASSWORD, "address": "Dhaka"}
    assert "do not match" in client.post("/register", data={**base, "confirm_password": "other123"}).text
    assert "Address is required" in client.post("/register", data={**base, "address": ""}).text
    assert "already exists" in client.post("/register", data={**base, "email": existing.email}).text


def test_login_required_redirects_back(client, make_user):
    r = client.get("/special-items", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login?next=/special-items"

    user = make_user(Role.RESIDENT)
    r = client.post("/login", data={"email": user.email, "password": PASSWORD, "next": "/special-items"},
                    follow_redirects=False)
    assert r.headers["location"] == "/special-items"

    # Open-redirect protection
    r = client.post("/login", data={"email": user.email, "password": PASSWORD, "next": "//evil.com"},
                    follow_redirects=False)
    assert r.headers["location"] == "/dashboard"


def test_role_based_navigation(client, as_role):
    as_role(Role.RESIDENT)
    page = client.get("/dashboard").text
    assert 'href="/special-items"' in page and 'href="/zones"' not in page and 'href="/sponsors"' not in page

    as_role(Role.ADMINISTRATOR)
    page = client.get("/dashboard").text
    for url in ("/materials", "/zones", "/centres", "/sponsors", "/special-items"):
        assert f'href="{url}"' in page


def test_404_page(client):
    r = client.get("/no-such-page", headers={"accept": "text/html"})
    assert r.status_code == 404 and "Page not found" in r.text
