"""AI Waste Scanner (extends #4). The real Gemini API is never called: tests replace it with a fake."""
import json

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import MaterialCategory, PreparationInstruction, Role
from app.services import waste_scan_service as scanner

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200  # starts with the JPEG signature


@pytest.fixture
def guide(db):
    food = MaterialCategory(name="Food Waste", examples="peels, rice", is_recyclable=True, is_biodegradable=True)
    food.instructions = [PreparationInstruction(step_no=1, instruction="Drain liquids")]
    plastic = MaterialCategory(name="Plastic Bottles", examples="water bottles", is_recyclable=True)
    db.add_all([food, plastic])
    db.commit()
    return {"food": food, "plastic": plastic}


@pytest.fixture
def fake_ai(monkeypatch):
    """fake_ai({"category": ...}) makes the scanner return that answer. Records what it was sent."""
    calls = []

    def _set(answer):
        def fake_classify(image, categories):
            calls.append({"image": image, "categories": [c.name for c in categories]})
            return answer
        monkeypatch.setattr(scanner, "classify_image", fake_classify)
        return calls

    return _set


def _scan(client, data=JPEG, filename="item.jpg"):
    return client.post("/materials/scan", files={"photo": (filename, data, "image/jpeg")})


def test_scan_needs_login(client):
    r = client.get("/materials/scan")
    assert r.url.path == "/login"
    assert _scan(client).url.path == "/login"


def test_scan_finds_biodegradable_item(client, as_role, guide, fake_ai):
    as_role(Role.RESIDENT)
    calls = fake_ai({"item": "banana peel", "category": "food waste", "confidence": "high",
                     "reason": "Fruit peel is organic."})
    r = _scan(client)
    assert r.status_code == 200
    assert "Food Waste" in r.text and "Biodegradable" in r.text and "Drain liquids" in r.text
    assert "banana peel" in r.text and "Confidence: high" in r.text
    assert f'href="/materials/{guide["food"].id}"' in r.text
    assert calls[0]["categories"] == ["Food Waste", "Plastic Bottles"]  # AI chooses from OUR list
    assert calls[0]["image"].mime_type == "image/jpeg"


def test_scan_non_biodegradable_and_low_confidence(client, as_role, guide, fake_ai):
    as_role(Role.COLLECTOR)
    fake_ai({"item": "bottle", "category": "Plastic Bottles", "confidence": "low", "reason": ""})
    r = _scan(client)
    assert "Non-biodegradable" in r.text and "not sure" in r.text


def test_scan_unknown_item(client, as_role, guide, fake_ai):
    as_role(Role.RESIDENT)
    fake_ai({"item": "a cat", "category": "unknown", "confidence": "high", "reason": "This is not waste."})
    r = _scan(client)
    assert "couldn't match" in r.text and "This is not waste." in r.text


def test_scan_rejects_bad_files_before_calling_ai(client, as_role, guide, fake_ai):
    as_role(Role.RESIDENT)
    calls = fake_ai({"category": "Food Waste"})
    r = _scan(client, data=b"MZ fake exe", filename="photo.jpg")
    assert r.status_code == 400 and "JPG, PNG or WEBP" in r.text
    r = _scan(client, data=JPEG + b"0" * (5 * 1024 * 1024))
    assert r.status_code == 400 and "5 MB" in r.text
    r = client.post("/materials/scan", data={})
    assert r.status_code == 400 and "take or choose a photo" in r.text
    assert calls == []


def test_scan_with_empty_guide(client, as_role, fake_ai):
    as_role(Role.RESIDENT)
    fake_ai({"category": "unknown"})
    assert "no materials yet" in _scan(client).text


def test_missing_api_key_gives_setup_message(client, as_role, guide, monkeypatch):
    as_role(Role.RESIDENT)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    r = _scan(client)
    assert r.status_code == 400 and "GEMINI_API_KEY" in r.text


def test_classify_image_sends_photo_and_category_list(guide, monkeypatch):
    """Checks the real request we build for Gemini, using a fake client instead of the internet."""
    from google import genai

    sent = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            sent.update(model=model, contents=contents, config=config)
            return type("Response", (), {"text": json.dumps({"item": "peel", "category": "Food Waste",
                                                             "confidence": "high", "reason": "ok"})})()

    class FakeClient:
        def __init__(self, api_key):
            sent["api_key"] = api_key
            self.models = FakeModels()

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(genai, "Client", FakeClient)

    image = scanner.Image(JPEG, ".jpg")
    answer = scanner.classify_image(image, [guide["food"], guide["plastic"]])

    assert answer["category"] == "Food Waste"
    assert sent["api_key"] == "test-key" and sent["model"] == settings.gemini_model
    assert sent["contents"][0].inline_data.data == JPEG
    assert sent["config"].response_mime_type == "application/json"
    enum = sent["config"].response_json_schema["properties"]["category"]["enum"]
    assert enum == ["Food Waste", "Plastic Bottles", "unknown"]


def test_admin_sets_biodegradable(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    data = {"name": "Leaves", "is_recyclable": "true", "is_biodegradable": "true", "points_per_kg": "1"}
    client.post("/materials/new", data=data)
    leaves = db.scalar(select(MaterialCategory).where(MaterialCategory.name == "Leaves"))
    assert leaves.is_biodegradable

    client.post(f"/materials/{leaves.id}/edit", data={"name": "Leaves", "points_per_kg": "0"})  # box unticked
    db.refresh(leaves)
    assert not leaves.is_biodegradable
