"""Feature #10: Collector & Service Zone Management (owner: Esha)

MVC files for this feature:
    Model      -> app/models/zone.py              ServiceZone (+ collector_zones link table, Collector M:N)
    Service    -> app/services/zone_service.py    rules (unique zone names, valid availability, ...)
    Controller -> this file                       URLs under /zones
    View       -> app/templates/zones/            HTML pages

Only Managers and Administrators can open these pages (role check on the whole router).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.dependencies import DbSession, found, require_roles
from app.models import Role
from app.services import zone_service as svc
from app.services.validation import ServiceError
from app.templating import flash, render

router = APIRouter(
    prefix="/zones",
    tags=["#10 Zones"],
    dependencies=[Depends(require_roles(Role.MANAGER, Role.ADMINISTRATOR))],
)

Text = Annotated[str, Form()]
Checkbox = Annotated[bool, Form()]
Ids = Annotated[list[int], Form()]


def _go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


@router.get("")
def zones_index(request: Request, db: DbSession):
    ctx = {"zones": svc.list_zones(db), "collectors": svc.list_collectors(db)}
    return render(request, "zones/index.html", ctx)


# ---------- Zones ----------


def _zone_form(request, db, *, zone=None, form=None, error=None, status_code=200):
    ctx = {"zone": zone, "form": form or {}, "error": error, "collectors": svc.list_collectors(db)}
    return render(request, "zones/zone_form.html", ctx, status_code=status_code)


@router.get("/new")
def zone_new_page(request: Request, db: DbSession):
    return _zone_form(request, db, form={"is_active": True, "collector_ids": []})


@router.post("/new")
def zone_create(
    request: Request, db: DbSession, name: Text = "", area_description: Text = "",
    is_active: Checkbox = False, collector_ids: Ids = [],
):
    form = {"name": name, "area_description": area_description, "is_active": is_active, "collector_ids": collector_ids}
    try:
        zone = svc.save_zone(db, None, **form)
    except ServiceError as e:
        return _zone_form(request, db, form=form, error=str(e), status_code=400)
    flash(request, f"Zone '{zone.name}' created.")
    return _go("/zones")


@router.get("/{zone_id}/edit")
def zone_edit_page(request: Request, db: DbSession, zone_id: int):
    zone = found(svc.get_zone(db, zone_id), "Zone")
    form = {"name": zone.name, "area_description": zone.area_description or "", "is_active": zone.is_active,
            "collector_ids": [c.id for c in zone.collectors]}
    return _zone_form(request, db, zone=zone, form=form)


@router.post("/{zone_id}/edit")
def zone_edit(
    request: Request, db: DbSession, zone_id: int, name: Text = "", area_description: Text = "",
    is_active: Checkbox = False, collector_ids: Ids = [],
):
    zone = found(svc.get_zone(db, zone_id), "Zone")
    form = {"name": name, "area_description": area_description, "is_active": is_active, "collector_ids": collector_ids}
    try:
        svc.save_zone(db, zone, **form)
    except ServiceError as e:
        return _zone_form(request, db, zone=zone, form=form, error=str(e), status_code=400)
    flash(request, "Zone updated.")
    return _go("/zones")


@router.post("/{zone_id}/delete")
def zone_delete(request: Request, db: DbSession, zone_id: int):
    zone = found(svc.get_zone(db, zone_id), "Zone")
    name = zone.name
    svc.delete_zone(db, zone)
    flash(request, f"Zone '{name}' deleted.", "info")
    return _go("/zones")


# ---------- Collectors ----------


@router.get("/collectors/new")
def collector_new_page(request: Request, db: DbSession):
    return render(request, "zones/collector_new.html", {"form": {"zone_ids": []}, "zones": svc.list_zones(db)})


@router.post("/collectors/new")
def collector_create(
    request: Request, db: DbSession, name: Text = "", email: Text = "", phone: Text = "", vehicle_no: Text = "",
    password: Text = "", confirm_password: Text = "", zone_ids: Ids = [],
):
    form = {"name": name, "email": email, "phone": phone, "vehicle_no": vehicle_no, "zone_ids": zone_ids}
    try:
        collector = svc.register_collector(db, password=password, confirm_password=confirm_password, **form)
    except ServiceError as e:
        ctx = {"form": form, "zones": svc.list_zones(db), "error": str(e)}
        return render(request, "zones/collector_new.html", ctx, status_code=400)
    flash(request, f"Collector {collector.name} registered. They can now log in with {collector.email}.")
    return _go("/zones#collectors")


def _collector_form(request, db, collector, form, error=None, status_code=200):
    ctx = {"collector": collector, "form": form, "error": error, "zones": svc.list_zones(db),
           "availability": svc.AVAILABILITY}
    return render(request, "zones/collector_edit.html", ctx, status_code=status_code)


@router.get("/collectors/{collector_id}/edit")
def collector_edit_page(request: Request, db: DbSession, collector_id: int):
    c = found(svc.get_collector(db, collector_id), "Collector")
    form = {"name": c.name, "phone": c.phone or "", "vehicle_no": c.vehicle_no or "",
            "availability_status": c.availability_status, "is_active": c.is_active, "zone_ids": [z.id for z in c.zones]}
    return _collector_form(request, db, c, form)


@router.post("/collectors/{collector_id}/edit")
def collector_edit(
    request: Request, db: DbSession, collector_id: int, name: Text = "", phone: Text = "", vehicle_no: Text = "",
    availability_status: Text = "", is_active: Checkbox = False, zone_ids: Ids = [],
):
    collector = found(svc.get_collector(db, collector_id), "Collector")
    form = {"name": name, "phone": phone, "vehicle_no": vehicle_no, "availability_status": availability_status,
            "is_active": is_active, "zone_ids": zone_ids}
    try:
        svc.update_collector(db, collector, **form)
    except ServiceError as e:
        return _collector_form(request, db, collector, form, str(e), status_code=400)
    flash(request, f"Collector {collector.name} updated.")
    return _go("/zones#collectors")
