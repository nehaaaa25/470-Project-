"""Shared check for uploaded photos (used by #5 special items and the AI waste scanner).

The file type is decided by the file's first bytes ("magic bytes"), never by its name,
so a renamed .exe cannot pose as a photo.
"""
from dataclasses import dataclass

from fastapi import UploadFile

from app.services.validation import ServiceError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
_SIGNATURES = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}
MIME_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@dataclass
class Image:
    data: bytes
    ext: str  # ".jpg", ".png" or ".webp"

    @property
    def mime_type(self) -> str:
        return MIME_TYPES[self.ext]


def read_image(upload: UploadFile) -> Image:
    """Read an uploaded photo, or raise ServiceError if it is too big or not a JPG/PNG/WEBP."""
    data = upload.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ServiceError("The photo must be 5 MB or smaller.")
    ext = next((e for sig, e in _SIGNATURES.items() if data.startswith(sig)), None)
    if ext is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    if ext is None:
        raise ServiceError("The photo must be a JPG, PNG or WEBP image.")
    return Image(data, ext)
