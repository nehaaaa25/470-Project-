"""Feature #14: Collection Centre Management (owner: Nowrin)

MVC files for this feature:
    Model      -> app/models/centre.py             CollectionCentre (+ centre_materials link table)
    Service    -> app/services/centre_service.py   rules (capacity must be > 0, at least one material, ...)
    Controller -> this file                        URLs under /centres
    View       -> app/templates/centres/           HTML pages

Everyone can browse active centres and filter them by accepted material.
Only administrators register, edit, deactivate or delete centres (and see inactive ones).
"""
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.dependencies import AdminUser, CurrentUser, DbSession, found
from app.models import Role
from app.services import centre_service as svc
from app.services import material_service
from app.services.validation import ServiceError
from app.templating import flash, render

router = APIRouter(prefix="/centres", tags=["#14 Centres"])

Text = Annotated[str, Form()]
Checkbox = Annotated[bool, Form()]
Ids = Annotated[list[int], Form()]


def _go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _is_admin(user) -> bool:
    return user is not None and user.role == Role.ADMINISTRATOR


@router.get("")
def centres_index(request: Request, db: DbSession, user: CurrentUser, q: str = "", material: str = ""):
    material_id = int(material) if material.isdigit() else None
    ctx = {
        "centres": svc.search_centres(db, keyword=q, material_id=material_id, include_inactive=_is_admin(user)),
        "materials": material_service.list_categories(db),
        "q": q,
        "material_id": material_id,
    }
    return render(request, "centres/index.html", ctx)


def _centre_form(request, db, *, centre=None, form=None, error=None, status_code=200):
    ctx = {"centre": centre, "form": form or {}, "error": error, "materials": material_service.list_categories(db)}
    return render(request, "centres/form.html", ctx, status_code=status_code)


@router.get("/new")
def centre_new_page(request: Request, db: DbSession, admin: AdminUser):
    return _centre_form(request, db, form={"is_active": True, "material_ids": []})


@router.post("/new")
def centre_create(
    request: Request, db: DbSession, admin: AdminUser, name: Text = "", address: Text = "", phone: Text = "",
    opening_hours: Text = "", processing_capacity_kg: Text = "", latitude: Text = "", longitude: Text = "",
    is_active: Checkbox = False, material_ids: Ids = [],
):
    form = {"name": name, "address": address, "phone": phone, "opening_hours": opening_hours,
            "processing_capacity_kg": processing_capacity_kg, "latitude": latitude, "longitude": longitude,
            "is_active": is_active, "material_ids": material_ids}
    try:
        centre = svc.save_centre(db, None, **form)
    except ServiceError as e:
        return _centre_form(request, db, form=form, error=str(e), status_code=400)
    flash(request, f"Centre '{centre.name}' registered.")
    return _go(f"/centres/{centre.id}")


@router.get("/{centre_id}")
def centre_detail(request: Request, db: DbSession, user: CurrentUser, centre_id: int):
    centre = found(svc.get_centre(db, centre_id), "Centre")
    if not centre.is_active and not _is_admin(user):
        found(None, "Centre")
    return render(request, "centres/detail.html", {"centre": centre})


@router.get("/{centre_id}/edit")
def centre_edit_page(request: Request, db: DbSession, admin: AdminUser, centre_id: int):
    c = found(svc.get_centre(db, centre_id), "Centre")
    form = {"name": c.name, "address": c.address, "phone": c.phone or "", "opening_hours": c.opening_hours,
            "processing_capacity_kg": f"{c.processing_capacity_kg:g}",
            "latitude": "" if c.latitude is None else f"{c.latitude:g}",
            "longitude": "" if c.longitude is None else f"{c.longitude:g}",
            "is_active": c.is_active, "material_ids": [m.id for m in c.materials]}
    return _centre_form(request, db, centre=c, form=form)


@router.post("/{centre_id}/edit")
def centre_edit(
    request: Request, db: DbSession, admin: AdminUser, centre_id: int, name: Text = "", address: Text = "",
    phone: Text = "", opening_hours: Text = "", processing_capacity_kg: Text = "", latitude: Text = "",
    longitude: Text = "", is_active: Checkbox = False, material_ids: Ids = [],
):
    centre = found(svc.get_centre(db, centre_id), "Centre")
    form = {"name": name, "address": address, "phone": phone, "opening_hours": opening_hours,
            "processing_capacity_kg": processing_capacity_kg, "latitude": latitude, "longitude": longitude,
            "is_active": is_active, "material_ids": material_ids}
    try:
        svc.save_centre(db, centre, **form)
    except ServiceError as e:
        return _centre_form(request, db, centre=centre, form=form, error=str(e), status_code=400)
    flash(request, "Centre updated.")
    return _go(f"/centres/{centre.id}")


@router.post("/{centre_id}/delete")
def centre_delete(request: Request, db: DbSession, admin: AdminUser, centre_id: int):
    centre = found(svc.get_centre(db, centre_id), "Centre")
    name = centre.name
    svc.delete_centre(db, centre)
    flash(request, f"Centre '{name}' deleted.", "info")
    return _go("/centres")
