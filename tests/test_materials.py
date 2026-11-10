"""Feature #4: Waste Sorting Guide & Material Catalogue."""
from sqlalchemy import func, select

from app.models import BinType, MaterialCategory, PreparationInstruction, Role


def _add_bin(client, name="Blue bin", colour="#1e6fd9"):
    return client.post("/materials/bins", data={"name": name, "colour": colour, "description": ""})


def _add_material(client, **overrides):
    data = {"name": "Paper", "description": "", "examples": "newspaper, boxes", "is_recyclable": "true",
            "points_per_kg": "5", "bin_type_id": "", "steps": "Remove tape\nFlatten boxes\n\nKeep dry"}
    data.update(overrides)
    return client.post("/materials/new", data=data)


def test_admin_builds_catalogue(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    assert "Bin type &#39;Blue bin&#39; added" in _add_bin(client).text
    bin_id = db.scalar(select(BinType.id))

    r = _add_material(client, bin_type_id=str(bin_id))
    assert r.status_code == 200 and "Material &#39;Paper&#39; added" in r.text
    category = db.scalar(select(MaterialCategory).where(MaterialCategory.name == "Paper"))
    assert [s.instruction for s in category.instructions] == ["Remove tape", "Flatten boxes", "Keep dry"]
    assert [s.step_no for s in category.instructions] == [1, 2, 3]
    assert category.bin_type.name == "Blue bin"


def test_catalogue_validation(client, as_role):
    as_role(Role.ADMINISTRATOR)
    _add_material(client)
    assert "already exists" in _add_material(client, name="PAPER").text
    assert "Name is required" in _add_material(client, name="  ").text
    r = _add_material(client, name="Diapers", is_recyclable="", points_per_kg="3")
    assert r.status_code == 400 and "cannot earn points" in r.text
    assert "whole number" in _add_material(client, name="Glass", points_per_kg="abc").text
    assert "hex colour" in _add_bin(client, name="Bad", colour="red").text


def test_steps_add_edit_move_delete(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    _add_material(client)
    category = db.scalar(select(MaterialCategory))
    cid = category.id
    s1, s2, s3 = [s.id for s in category.instructions]

    client.post(f"/materials/{cid}/steps", data={"instruction": "Bundle with string"})
    client.post(f"/materials/{cid}/steps/{s1}/edit", data={"instruction": "Remove plastic tape"})
    client.post(f"/materials/{cid}/steps/{s3}/move", data={"direction": "up"})
    client.post(f"/materials/{cid}/steps/{s2}/delete")

    db.expire_all()
    steps = db.scalars(select(PreparationInstruction).where(PreparationInstruction.category_id == cid)
                       .order_by(PreparationInstruction.step_no)).all()
    assert [(s.step_no, s.instruction) for s in steps] == [
        (1, "Remove plastic tape"), (2, "Keep dry"), (3, "Bundle with string"),
    ]


def test_delete_rules(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    _add_bin(client)
    bin_id = db.scalar(select(BinType.id))
    _add_material(client, bin_type_id=str(bin_id))
    cid = db.scalar(select(MaterialCategory.id))

    r = client.post(f"/materials/bins/{bin_id}/delete")
    assert "still used by: Paper" in r.text
    assert db.get(BinType, bin_id) is not None

    client.post(f"/materials/{cid}/delete")
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(MaterialCategory)) == 0
    assert db.scalar(select(func.count()).select_from(PreparationInstruction)) == 0  # composition

    assert "Bin type deleted" in client.post(f"/materials/bins/{bin_id}/delete").text


def test_public_browse_and_search(client, as_role):
    as_role(Role.ADMINISTRATOR)
    _add_bin(client, "Yellow bin", "#f2c200")
    _add_material(client)
    _add_material(client, name="Plastic Bottles", examples="water bottles", steps="Rinse with water")
    client.post("/logout")

    page = client.get("/materials").text  # no login needed
    assert "Paper" in page and "Plastic Bottles" in page and "Add material" not in page

    by_example = client.get("/materials", params={"q": "newspaper"}).text
    assert "Paper" in by_example and "Plastic Bottles" not in by_example
    by_step = client.get("/materials", params={"q": "rinse"}).text
    assert "Plastic Bottles" in by_step and "Paper</a>" not in by_step
    assert "No materials match" in client.get("/materials", params={"q": "zzz"}).text


def test_only_admin_can_manage(client, as_role):
    assert client.get("/materials/new", follow_redirects=False).status_code == 303  # not logged in
    as_role(Role.RESIDENT)
    assert client.get("/materials/new").status_code == 403
    assert _add_material(client).status_code == 403
    as_role(Role.MANAGER)
    assert client.get("/materials/bins").status_code == 403
