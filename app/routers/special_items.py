"""Feature #5: Special Item Collection Requests (owner: Neha)

MVC files for this feature:
    Model      -> app/models/special_item.py            SpecialItemRequest, SpecialistService
    Service    -> app/services/special_item_service.py  rules (status flow, matching service type, ...)
    Controller -> this file                             URLs under /special-items
    View       -> app/templates/special_items/          HTML pages

Residents submit and track their own requests.
Managers and administrators review requests and manage the specialist services list.

Note: /special-items/new and /special-items/services are declared before /special-items/{request_id}.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from app.dependencies import DbSession, LoggedInUser, StaffUser, found, require_roles
from app.models import ItemType, RequestStatus, Role, User
from app.services import special_item_service as svc
from app.services.validation import ServiceError
from app.templating import flash, render

router = APIRouter(
    prefix="/special-items",
    tags=["#5 Special items"],
    dependencies=[Depends(require_roles(Role.RESIDENT, Role.MANAGER, Role.ADMINISTRATOR))],
)

Text = Annotated[str, Form()]
Checkbox = Annotated[bool, Form()]
ResidentUser = Annotated[User, Depends(require_roles(Role.RESIDENT))]


def _go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _load_request(db, request_id: int, user: User):
    item = found(svc.get_request(db, request_id), "Request")
    if not svc.can_view(user, item):
        raise HTTPException(status_code=403, detail="You can only view your own requests.")
    return item


@router.get("")
def special_items_index(request: Request, db: DbSession, user: LoggedInUser, status: str = ""):
    status = status if status in {s.value for s in RequestStatus} else ""
    if svc.is_reviewer(user):
        ctx = {"requests": svc.list_requests(db, status=status), "counts": svc.count_by_status(db),
               "status": status, "reviewer": True}
    else:
        ctx = {"requests": svc.list_requests(db, resident=user, status=status),
               "counts": svc.count_by_status(db, resident=user), "status": status, "reviewer": False}
    return render(request, "special_items/index.html", ctx)


# ---------- Resident: new request ----------


@router.get("/new")
def request_new_page(request: Request, user: ResidentUser):
    form = {"item_type": ItemType.BULKY.value, "pickup_address": user.address}
    return render(request, "special_items/new.html", {"form": form, "item_types": list(ItemType)})


@router.post("/new")
def request_create(
    request: Request, db: DbSession, user: ResidentUser, item_type: Text = "", description: Text = "",
    pickup_address: Text = "", photo: Annotated[UploadFile | None, File()] = None,
):
    form = {"item_type": item_type, "description": description, "pickup_address": pickup_address}
    try:
        item = svc.submit_request(db, user, photo=photo, **form)
    except ServiceError as e:
        ctx = {"form": form, "item_types": list(ItemType), "error": str(e)}
        return render(request, "special_items/new.html", ctx, status_code=400)
    flash(request, f"Request #{item.id} submitted. Staff will review it soon.")
    return _go(f"/special-items/{item.id}")


# ---------- Staff: specialist services ----------


def _services_page(request, db, *, form=None, error=None, status_code=200):
    ctx = {"services": svc.list_services(db), "item_types": list(ItemType), "error": error,
           "form": form or {"service_type": ItemType.BULKY.value, "is_active": True}}
    return render(request, "special_items/services.html", ctx, status_code=status_code)


@router.get("/services")
def services_page(request: Request, db: DbSession, staff: StaffUser):
    return _services_page(request, db)


@router.post("/services")
def service_create(
    request: Request, db: DbSession, staff: StaffUser, name: Text = "", service_type: Text = "",
    contact_phone: Text = "", email: Text = "", notes: Text = "", is_active: Checkbox = False,
):
    form = {"name": name, "service_type": service_type, "contact_phone": contact_phone, "email": email,
            "notes": notes, "is_active": is_active}
    try:
        service = svc.save_service(db, None, **form)
    except ServiceError as e:
        return _services_page(request, db, form=form, error=str(e), status_code=400)
    flash(request, f"Specialist service '{service.name}' added.")
    return _go("/special-items/services")


@router.get("/services/{service_id}/edit")
def service_edit_page(request: Request, db: DbSession, staff: StaffUser, service_id: int):
    s = found(svc.get_service(db, service_id), "Service")
    form = {"name": s.name, "service_type": s.service_type, "contact_phone": s.contact_phone,
            "email": s.email or "", "notes": s.notes or "", "is_active": s.is_active}
    return render(request, "special_items/service_edit.html", {"service": s, "form": form, "item_types": list(ItemType)})


@router.post("/services/{service_id}/edit")
def service_edit(
    request: Request, db: DbSession, staff: StaffUser, service_id: int, name: Text = "", service_type: Text = "",
    contact_phone: Text = "", email: Text = "", notes: Text = "", is_active: Checkbox = False,
):
    service = found(svc.get_service(db, service_id), "Service")
    form = {"name": name, "service_type": service_type, "contact_phone": contact_phone, "email": email,
            "notes": notes, "is_active": is_active}
    try:
        svc.save_service(db, service, **form)
    except ServiceError as e:
        ctx = {"service": service, "form": form, "item_types": list(ItemType), "error": str(e)}
        return render(request, "special_items/service_edit.html", ctx, status_code=400)
    flash(request, "Specialist service updated.")
    return _go("/special-items/services")


@router.post("/services/{service_id}/delete")
def service_delete(request: Request, db: DbSession, staff: StaffUser, service_id: int):
    service = found(svc.get_service(db, service_id), "Service")
    try:
        svc.delete_service(db, service)
        flash(request, "Specialist service deleted.", "info")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go("/special-items/services")


# ---------- One request ----------


@router.get("/{request_id}")
def request_detail(request: Request, db: DbSession, user: LoggedInUser, request_id: int):
    item = _load_request(db, request_id, user)
    ctx = {"item": item, "reviewer": svc.is_reviewer(user)}
    if ctx["reviewer"] and item.is_pending:
        ctx["matching_services"] = svc.list_services(db, item_type=item.item_type, active_only=True)
    return render(request, "special_items/detail.html", ctx)


@router.get("/{request_id}/photo")
def request_photo(db: DbSession, user: LoggedInUser, request_id: int):
    item = _load_request(db, request_id, user)
    path = found(svc.photo_file(item), "Photo")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{request_id}/approve")
def request_approve(
    request: Request, db: DbSession, staff: StaffUser, request_id: int, service_id: Text = "", note: Text = "",
):
    item = _load_request(db, request_id, staff)
    try:
        svc.approve(db, item, staff, service_id=service_id, note=note)
        flash(request, f"Request #{item.id} approved and referred to {item.specialist_service.name}.")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go(f"/special-items/{item.id}")


@router.post("/{request_id}/reject")
def request_reject(request: Request, db: DbSession, staff: StaffUser, request_id: int, note: Text = ""):
    item = _load_request(db, request_id, staff)
    try:
        svc.reject(db, item, staff, note=note)
        flash(request, f"Request #{item.id} rejected.", "info")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go(f"/special-items/{item.id}")


@router.post("/{request_id}/cancel")
def request_cancel(request: Request, db: DbSession, user: ResidentUser, request_id: int):
    item = _load_request(db, request_id, user)
    try:
        svc.cancel(db, item, user)
        flash(request, f"Request #{item.id} cancelled.", "info")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go(f"/special-items/{item.id}")
