"""AI Waste Scanner (extends #4 Sorting Guide, owner: Neha)

Flow:  photo  ->  Gemini picks ONE material category from our own list  ->  our sorting guide for it

The AI only recognises the item. Everything the user is told afterwards (bin, biodegradable or not,
preparation steps) comes from the categories the administrator manages, so the AI cannot invent advice.
The photo is checked, sent to Gemini and then forgotten; EcoWaste does not store it.
"""
import json
import logging
from dataclasses import dataclass

from fastapi import UploadFile

from app.config import settings
from app.models import MaterialCategory
from app.services import material_service
from app.services.images import Image, read_image
from app.services.validation import ServiceError

log = logging.getLogger(__name__)

UNKNOWN = "unknown"
CONFIDENCE_LEVELS = ("high", "medium", "low")


@dataclass
class ScanResult:
    image: Image
    item: str  # what the AI saw, e.g. "crushed plastic water bottle"
    category: MaterialCategory | None  # None = no match in our guide
    confidence: str  # high / medium / low
    reason: str


def scan(db, photo: UploadFile | None) -> ScanResult:
    if photo is None or not photo.filename:
        raise ServiceError("Please take or choose a photo of the item.")
    image = read_image(photo)

    categories = material_service.list_categories(db)
    if not categories:
        raise ServiceError("The sorting guide has no materials yet, so there is nothing to match the photo against.")

    answer = classify_image(image, categories)

    by_name = {c.name.lower(): c for c in categories}
    category = by_name.get(str(answer.get("category", "")).strip().lower())
    confidence = answer.get("confidence") if answer.get("confidence") in CONFIDENCE_LEVELS else "low"
    return ScanResult(
        image=image,
        item=str(answer.get("item") or "").strip()[:120],
        category=category,
        confidence=confidence,
        reason=str(answer.get("reason") or "").strip()[:300],
    )


def _prompt(categories: list[MaterialCategory]) -> str:
    lines = [f"- {c.name}: {c.examples or c.description or ''}".rstrip(": ") for c in categories]
    return (
        "You are the photo scanner of a waste sorting guide in Dhaka, Bangladesh.\n"
        "Look at the photo and decide which ONE of these material categories the main item belongs to:\n"
        + "\n".join(lines)
        + f"\n\nIf the photo does not show waste, is too unclear, or fits none of the categories, "
        f"answer \"{UNKNOWN}\". If there are several items, judge the most prominent one.\n"
        "item: a short description of what you see (max 8 words).\n"
        "reason: one short sentence explaining your choice, written for the resident."
    )


def _schema(categories: list[MaterialCategory]) -> dict:
    return {
        "type": "object",
        "properties": {
            "item": {"type": "string"},
            "category": {"type": "string", "enum": [c.name for c in categories] + [UNKNOWN]},
            "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
            "reason": {"type": "string"},
        },
        "required": ["item", "category", "confidence", "reason"],
    }


def classify_image(image: Image, categories: list[MaterialCategory]) -> dict:
    """Ask Gemini which category the photo shows. Returns {"item", "category", "confidence", "reason"}.
    Tests replace this function, so they never call the real AI."""
    if not settings.gemini_api_key:
        raise ServiceError("The scanner is not set up yet. Add GEMINI_API_KEY to the .env file and restart the app.")

    from google import genai  # imported here so the rest of the app works even without the package
    from google.genai import errors, types

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Part.from_bytes(data=image.data, mime_type=image.mime_type), _prompt(categories)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",  # answer only in the JSON shape below
                response_json_schema=_schema(categories),
            ),
        )
    except errors.APIError as e:
        log.warning("Gemini API error %s: %s", getattr(e, "code", "?"), getattr(e, "message", e))
        if getattr(e, "code", None) == 429:
            raise ServiceError("The free AI limit has been reached for now. Please wait a minute and try again.") from None
        if getattr(e, "code", None) in (400, 401, 403):
            raise ServiceError("The AI service rejected the request. Check GEMINI_API_KEY and GEMINI_MODEL in .env.") from None
        raise ServiceError("The AI service is not responding right now. Please try again later.") from None
    except Exception:  # network problems, timeouts
        log.exception("Could not reach Gemini")
        raise ServiceError("Could not reach the AI service. Check your internet connection and try again.") from None

    try:
        answer = json.loads(response.text or "")
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        raise ServiceError("The AI gave an answer we could not read. Please try again.")
    return answer
