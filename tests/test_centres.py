"""Feature #14: Collection Centre Management."""
from sqlalchemy import select

from app.models import CollectionCentre, MaterialCategory, Role


def _materials(db, *names):
    items = [MaterialCategory(name=n) for n in names]
    db.add_all(items)
    db.commit()
    return [m.id for m in items]


def _centre(client, material_ids, **overrides):
    data = {"name": "Mohakhali Hub", "address": "Plot 7, Mohakhali", "phone": "", "opening_hours": "Sat-Thu 9-5",
            "processing_capacity_kg": "2500", "latitude": "23.7781", "longitude": "90.4057", "is_active": "true",
            "material_ids": [str(i) for i in material_ids]}
    data.update(overrides)
    return client.post("/centres/new", data=data)


def test_admin_registers_centre(client, db, as_role):
    paper, glass = _materials(db, "Paper", "Glass")
    as_role(Role.ADMINISTRATOR)
    r = _centre(client, [paper, glass])
    assert r.status_code == 200 and "Centre &#39;Mohakhali Hub&#39; registered" in r.text
    assert "2,500 kg per day" in r.text and "Paper" in r.text and "Glass" in r.text

    centre = db.scalar(select(CollectionCentre))
    assert centre.latitude == 23.7781 and centre.accepts_material(db.get(MaterialCategory, paper))


def test_centre_validation(client, db, as_role):
    (paper,) = _materials(db, "Paper")
    as_role(Role.ADMINISTRATOR)
    assert "greater than 0" in _centre(client, [paper], processing_capacity_kg="0").text
    assert "at least one accepted material" in _centre(client, []).text
    assert "both latitude and longitude" in _centre(client, [paper], longitude="").text
    assert "Latitude must be at most 90" in _centre(client, [paper], latitude="123").text
    assert "Opening hours is required" in _centre(client, [paper], opening_hours="").text
    _centre(client, [paper])
    assert "already exists" in _centre(client, [paper], name="MOHAKHALI HUB").text


def test_public_list_filter_and_inactive(client, db, as_role):
    paper, ewaste = _materials(db, "Paper", "E-waste")
    as_role(Role.ADMINISTRATOR)
    _centre(client, [paper], name="Paper Point")
    _centre(client, [ewaste], name="E-Centre")
    _centre(client, [paper, ewaste], name="Closed Centre", is_active="")
    closed_id = db.scalar(select(CollectionCentre.id).where(CollectionCentre.name == "Closed Centre"))

    assert "Closed Centre" in client.get("/centres").text  # admin sees inactive
    client.post("/logout")

    page = client.get("/centres").text  # visitors can browse without logging in
    assert "Paper Point" in page and "E-Centre" in page and "Closed Centre" not in page
    filtered = client.get("/centres", params={"material": ewaste}).text
    assert "E-Centre" in filtered and "Paper Point" not in filtered
    assert client.get(f"/centres/{closed_id}").status_code == 404


def test_edit_and_delete(client, db, as_role):
    paper, glass = _materials(db, "Paper", "Glass")
    as_role(Role.ADMINISTRATOR)
    _centre(client, [paper])
    cid = db.scalar(select(CollectionCentre.id))
    client.post(f"/centres/{cid}/edit", data={
        "name": "Hub 2", "address": "New address", "opening_hours": "Daily", "processing_capacity_kg": "100",
        "material_ids": [str(glass)],
    })
    db.expire_all()
    centre = db.get(CollectionCentre, cid)
    assert (centre.name, centre.latitude, centre.is_active) == ("Hub 2", None, False)
    assert [m.name for m in centre.materials] == ["Glass"]

    client.post(f"/centres/{cid}/delete")
    db.expire_all()
    assert db.get(CollectionCentre, cid) is None
    assert db.get(MaterialCategory, glass) is not None


def test_only_admin_manages(client, db, as_role):
    (paper,) = _materials(db, "Paper")
    as_role(Role.MANAGER)
    assert client.get("/centres/new").status_code == 403
    assert _centre(client, [paper]).status_code == 403
