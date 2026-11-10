"""Small helpers that turn raw form text into clean values, or raise a friendly error.

Every service uses them, so all forms behave the same way:

    name = validation.text(form_name, "Name", max_len=80)
    qty  = validation.integer(form_qty, "Quantity", min_value=1)
"""
from datetime import date


class ServiceError(ValueError):
    """A business rule was broken. The message is shown to the user as-is."""


def text(value: str | None, label: str, *, required: bool = True, max_len: int = 255) -> str | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise ServiceError(f"{label} is required.")
        return None
    if len(value) > max_len:
        raise ServiceError(f"{label} must be at most {max_len} characters.")
    return value


def integer(
    value: str | int | None, label: str, *, required: bool = True,
    min_value: int | None = None, max_value: int | None = None,
) -> int | None:
    raw = str(value).strip() if value is not None else ""
    if not raw:
        if required:
            raise ServiceError(f"{label} is required.")
        return None
    try:
        number = int(raw)
    except ValueError:
        raise ServiceError(f"{label} must be a whole number.") from None
    if min_value is not None and number < min_value:
        raise ServiceError(f"{label} must be at least {min_value}.")
    if max_value is not None and number > max_value:
        raise ServiceError(f"{label} must be at most {max_value}.")
    return number


def number(
    value: str | float | None, label: str, *, required: bool = True,
    min_value: float | None = None, max_value: float | None = None, exclusive_min: bool = False,
) -> float | None:
    raw = str(value).strip() if value is not None else ""
    if not raw:
        if required:
            raise ServiceError(f"{label} is required.")
        return None
    try:
        result = float(raw)
    except ValueError:
        raise ServiceError(f"{label} must be a number.") from None
    if result != result or result in (float("inf"), float("-inf")):  # NaN / infinity
        raise ServiceError(f"{label} must be a number.")
    if min_value is not None:
        if exclusive_min and result <= min_value:
            raise ServiceError(f"{label} must be greater than {min_value:g}.")
        if not exclusive_min and result < min_value:
            raise ServiceError(f"{label} must be at least {min_value:g}.")
    if max_value is not None and result > max_value:
        raise ServiceError(f"{label} must be at most {max_value:g}.")
    return result


def date_value(value: str | None, label: str) -> date:
    raw = (value or "").strip()
    if not raw:
        raise ServiceError(f"{label} is required.")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ServiceError(f"{label} must be a valid date (YYYY-MM-DD).") from None


def hex_colour(value: str | None, label: str = "Colour") -> str:
    raw = (value or "").strip()
    if len(raw) == 7 and raw[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in raw[1:]):
        return raw.lower()
    raise ServiceError(f"{label} must be a hex colour like #2e7d4f.")


def choice(value: str | None, label: str, allowed) -> str:
    raw = (value or "").strip()
    if raw not in {str(a) for a in allowed}:
        raise ServiceError(f"Please choose a valid {label.lower()}.")
    return raw
