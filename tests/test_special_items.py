"""Feature #5: Special Item Collection Requests."""
from sqlalchemy import select

from app.models import Role, SpecialistService, SpecialItemRequest
from tests.conftest import login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _submit(client, item_type="electronic", description="Old CRT TV", photo=None):
    files = {"photo": ("tv.png", photo, "image/png")} if photo is not None else None
    return client.post("/special-items/new", files=files, data={
        "item_type": item_type, "description": description, "pickup_address": "House 1, Dhaka",
    })


def _service(db, name="E-Cycle", service_type="electronic", active=True):
    service = SpecialistService(name=name, service_type=service_type, contact_phone="01800", is_active=active)
    db.add(service)
    db.commit()
    return service


def test_resident_submits_and_tracks(client, db, as_role):
    resident = as_role(Role.RESIDENT)
    form = client.get("/special-items/new").text
    assert "House 1, Road 2, Dhaka" in form  # pickup address pre-filled from profile

    r = _submit(client, photo=PNG)
    assert "submitted" in r.text and "Waiting for staff review" in r.text
    item = db.scalar(select(SpecialItemRequest))
    assert (item.resident_id, item.status, item.item_type) == (resident.id, "pending", "electronic")
    assert item.photo_path.endswith(".png")
    assert client.get(f"/special-items/{item.id}/photo").content == PNG

    page = client.get("/special-items").text
    assert "Electronic waste" in page and "Old CRT TV" in page


def test_submit_validation(client, as_role):
    as_role(Role.RESIDENT)
    assert "Description is required" in _submit(client, description=" ").text
    assert "valid item type" in _submit(client, item_type="nuclear").text
    r = _submit(client, photo=b"MZ this is not an image")
    assert r.status_code == 400 and "JPG, PNG or WEBP" in r.text


def test_privacy_between_residents(client, db, as_role):
    as_role(Role.RESIDENT)
    _submit(client, photo=PNG)
    item_id = db.scalar(select(SpecialItemRequest.id))

    as_role(Role.RESIDENT)
    assert client.get(f"/special-items/{item_id}").status_code == 403
    assert client.get(f"/special-items/{item_id}/photo").status_code == 403
    assert "Old CRT TV" not in client.get("/special-items").text

    as_role(Role.COLLECTOR)
    assert client.get("/special-items").status_code == 403


def test_manager_approves_with_matching_service(client, db, make_user, as_role):
    resident = make_user(Role.RESIDENT)
    login(client, resident.email)
    _submit(client)
    item_id = db.scalar(select(SpecialItemRequest.id))
    ecycle = _service(db)
    movers = _service(db, "BulkAway", "bulky")
    closed = _service(db, "Old E-waste", "electronic", active=False)

    manager = as_role(Role.MANAGER)
    page = client.get(f"/special-items/{item_id}").text
    assert "E-Cycle" in page and "BulkAway" not in page and "Old E-waste" not in page

    assert "handles bulky item" in client.post(f"/special-items/{item_id}/approve",
                                               data={"service_id": str(movers.id)}).text
    assert "active specialist service" in client.post(f"/special-items/{item_id}/approve",
                                                      data={"service_id": str(closed.id)}).text

    r = client.post(f"/special-items/{item_id}/approve", data={"service_id": str(ecycle.id), "note": "Call them"})
    assert "approved and referred to E-Cycle" in r.text
    db.expire_all()
    item = db.get(SpecialItemRequest, item_id)
    assert (item.status, item.specialist_service_id, item.reviewed_by_id) == ("approved", ecycle.id, manager.id)
    assert item.reviewed_at is not None

    # Cannot review twice; resident cannot cancel an approved request
    assert "already approved" in client.post(f"/special-items/{item_id}/reject", data={"note": "x"}).text
    login(client, resident.email)
    page = client.get(f"/special-items/{item_id}").text
    assert "E-Cycle" in page and "Call them" in page
    assert "Only pending" in client.post(f"/special-items/{item_id}/cancel").text


def test_reject_needs_reason_and_cancel(client, db, make_user, as_role):
    resident = make_user(Role.RESIDENT)
    login(client, resident.email)
    _submit(client, description="Paint cans")
    _submit(client, description="Sofa", item_type="bulky")
    paint_id, sofa_id = db.scalars(select(SpecialItemRequest.id).order_by(SpecialItemRequest.id)).all()

    assert client.post(f"/special-items/{paint_id}/approve", data={"service_id": "1"}).status_code == 403
    assert "cancelled" in client.post(f"/special-items/{sofa_id}/cancel").text

    as_role(Role.ADMINISTRATOR)
    assert "Reason for rejection is required" in client.post(f"/special-items/{paint_id}/reject",
                                                             data={"note": ""}).text
    client.post(f"/special-items/{paint_id}/reject", data={"note": "Not in our service area"})
    db.expire_all()
    assert db.get(SpecialItemRequest, paint_id).status == "rejected"
    assert db.get(SpecialItemRequest, sofa_id).status == "cancelled"
    assert "Paint cans" in client.get("/special-items", params={"status": "rejected"}).text


def test_specialist_service_management(client, db, make_user, as_role):
    as_role(Role.MANAGER)
    r = client.post("/special-items/services", data={
        "name": "SafeHaz", "service_type": "hazardous", "contact_phone": "01800", "email": "bad-email",
        "notes": "", "is_active": "true",
    })
    assert "valid email" in r.text
    r = client.post("/special-items/services", data={
        "name": "SafeHaz", "service_type": "hazardous", "contact_phone": "01800", "email": "", "notes": "",
        "is_active": "true",
    })
    assert "SafeHaz" in r.text
    service = db.scalar(select(SpecialistService))

    # A service that received a referral cannot be deleted
    resident = make_user(Role.RESIDENT)
    db.add(SpecialItemRequest(resident_id=resident.id, item_type="hazardous", description="Acid",
                              pickup_address="Dhaka", status="approved", specialist_service_id=service.id))
    db.commit()
    assert "cannot be deleted" in client.post(f"/special-items/services/{service.id}/delete").text

    as_role(Role.RESIDENT)
    assert client.get("/special-items/services").status_code == 403
