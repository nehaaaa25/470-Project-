"""VIEW helper: render Jinja2 templates with the logged-in user and flash messages."""
from datetime import date
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, settings
from app.features import FEATURES, can_open

templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
templates.env.globals.update(settings=settings, FEATURES=FEATURES, can_open=can_open, today=date.today)


def has_role(user, *roles: str) -> bool:
    """In templates: {% if has_role(current_user, 'administrator') %} ... {% endif %}"""
    return user is not None and user.role in roles


def pairs(items, label: str = "name", value: str = "id") -> list[tuple]:
    """In templates: bin_types|pairs  ->  [(1, "Blue bin"), (2, "Green bin")] for <select> options."""
    return [(getattr(i, value), getattr(i, label)) for i in items]


templates.env.globals["has_role"] = has_role
templates.env.filters["pairs"] = pairs


def flash(request: Request, message: str, category: str = "success") -> None:
    """Show a one-time message on the next page. category = Bootstrap colour (success, danger, ...)."""
    request.session.setdefault("_flashes", []).append({"message": message, "category": category})


def render(request: Request, name: str, context: dict[str, Any] | None = None, status_code: int = 200):
    ctx = {
        "current_user": getattr(request.state, "user", None),
        "flashes": request.session.pop("_flashes", []),
    }
    ctx.update(context or {})
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
