"""Feature #10: Collector & Service Zone Management."""
from sqlalchemy import select

from app.models import Collector, Role, ServiceZone
from tests.conftest import PASSWORD, login


def _zone(client, name="Mohakhali", collector_ids=(), active=True):
    data = {"name": name, "area_description": "DOHS area", "collector_ids": [str(i) for i in collector_ids]}
    if active:
        data["is_active"] = "true"
    return client.post("/zones/new", data=data)


def _collector(client, email="rahim@test.com", zone_ids=(), **overrides):
    data = {"name": "Rahim", "email": email, "phone": "01700", "vehicle_no": "DHA-1", "password": PASSWORD,
            "confirm_password": PASSWORD, "zone_ids": [str(i) for i in zone_ids]}
    data.update(overrides)
    return client.post("/zones/collectors/new", data=data)


def test_only_managers_and_admins(client, as_role):
    as_role(Role.RESIDENT)
    assert client.get("/zones").status_code == 403
    as_role(Role.COLLECTOR)
    assert client.get("/zones").status_code == 403
    as_role(Role.MANAGER)
    assert client.get("/zones").status_code == 200
    as_role(Role.ADMINISTRATOR)
    assert client.get("/zones").status_code == 200


def test_register_collector_with_zones(client, db, as_role):
    as_role(Role.MANAGER)
    _zone(client, "Mohakhali")
    _zone(client, "Banani")
    zone_ids = db.scalars(select(ServiceZone.id).order_by(ServiceZone.name)).all()

    r = _collector(client, zone_ids=zone_ids)
    assert "Collector Rahim registered" in r.text

    collector = db.scalar(select(Collector))
    assert sorted(z.name for z in collector.zones) == ["Banani", "Mohakhali"]

    # The collector can log in and sees their zones on the dashboard
    page = login(client, "rahim@test.com").text
    assert "Your service zones" in page and "Banani" in page


def test_zone_validation(client, as_role):
    as_role(Role.ADMINISTRATOR)
    _zone(client, "Gulshan")
    assert "already exists" in _zone(client, "gulshan").text
    assert "Zone name is required" in _zone(client, "").text
    assert "does not exist" in _zone(client, "X", collector_ids=[999]).text
    assert "do not match" in _collector(client, confirm_password="nope1234").text
    _collector(client)
    assert "already exists" in _collector(client).text


def test_edit_collector_and_deactivate(client, db, as_role):
    as_role(Role.MANAGER)
    _zone(client, "Banani")
    _collector(client)
    collector = db.scalar(select(Collector))
    zone = db.scalar(select(ServiceZone))

    r = client.post(f"/zones/collectors/{collector.id}/edit", data={
        "name": "Rahim Uddin", "phone": "", "vehicle_no": "DHA-2", "availability_status": "on_leave",
        "zone_ids": [str(zone.id)],  # is_active unticked
    })
    assert "Collector Rahim Uddin updated" in r.text
    db.expire_all()
    collector = db.get(Collector, collector.id)
    assert (collector.availability_status, collector.is_active, collector.vehicle_no) == ("on_leave", False, "DHA-2")
    assert [z.name for z in collector.zones] == ["Banani"]

    bad = client.post(f"/zones/collectors/{collector.id}/edit", data={"name": "R", "availability_status": "flying"})
    assert bad.status_code == 400 and "valid availability" in bad.text

    client.post("/logout")
    assert client.post("/login", data={"email": "rahim@test.com", "password": PASSWORD}).status_code == 400


def test_edit_and_delete_zone(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    _collector(client)
    collector_id = db.scalar(select(Collector.id))
    _zone(client, "Banani")
    zone_id = db.scalar(select(ServiceZone.id))

    client.post(f"/zones/{zone_id}/edit", data={"name": "Banani North", "collector_ids": [str(collector_id)]})
    db.expire_all()
    zone = db.get(ServiceZone, zone_id)
    assert zone.name == "Banani North" and not zone.is_active and [c.id for c in zone.collectors] == [collector_id]

    assert "deleted" in client.post(f"/zones/{zone_id}/delete").text
    db.expire_all()
    assert db.get(ServiceZone, zone_id) is None
    assert db.get(Collector, collector_id).zones == []  # collector is kept, link removed
