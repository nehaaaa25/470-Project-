"""Feature #4: Waste Sorting Guide & Material Catalogue (owner: Neha)

MVC files for this feature:
    Model      -> app/models/material.py            MaterialCategory, PreparationInstruction, BinType
    Service    -> app/services/material_service.py  rules (unique names, steps numbered 1..n, ...)
    Controller -> this file                         URLs under /materials
    View       -> app/templates/materials/          HTML pages

Everyone (even logged-out visitors) can browse and search the guide.
Only administrators can add, edit or delete categories, steps and bin types.

Note: fixed paths like /materials/bins and /materials/new are declared before
/materials/{category_id}, so they are matched first.
"""
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.dependencies import AdminUser, DbSession, found
from app.services import material_service as svc
from app.services.validation import ServiceError
from app.templating import flash, render

router = APIRouter(prefix="/materials", tags=["#4 Materials"])

# Form fields default to "" so a missing field gives a friendly message from the service, not a raw 422 error.
Text = Annotated[str, Form()]
OptionalText = Text


def _go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------- Public guide ----------


@router.get("")
def materials_index(request: Request, db: DbSession, q: str = "", bin: str = ""):
    bin_id = int(bin) if bin.isdigit() else None
    ctx = {
        "categories": svc.search_categories(db, q, bin_id),
        "bin_types": svc.list_bin_types(db),
        "q": q,
        "bin_id": bin_id,
    }
    return render(request, "materials/index.html", ctx)


# ---------- Bin types (admin) ----------


@router.get("/bins")
def bins_page(request: Request, db: DbSession, admin: AdminUser):
    return render(request, "materials/bins.html", {"bin_types": svc.list_bin_types(db), "form": {"colour": "#2e7d4f"}})


@router.post("/bins")
def bins_create(
    request: Request, db: DbSession, admin: AdminUser,
    name: Text = "", colour: Text = "#6c757d", description: OptionalText = "",
):
    try:
        bin_type = svc.save_bin_type(db, None, name=name, colour=colour, description=description)
    except ServiceError as e:
        ctx = {"bin_types": svc.list_bin_types(db), "error": str(e),
               "form": {"name": name, "colour": colour, "description": description}}
        return render(request, "materials/bins.html", ctx, status_code=400)
    flash(request, f"Bin type '{bin_type.name}' added.")
    return _go("/materials/bins")


@router.get("/bins/{bin_id}/edit")
def bin_edit_page(request: Request, db: DbSession, admin: AdminUser, bin_id: int):
    bin_type = found(svc.get_bin_type(db, bin_id), "Bin type")
    form = {"name": bin_type.name, "colour": bin_type.colour, "description": bin_type.description or ""}
    return render(request, "materials/bin_form.html", {"bin_type": bin_type, "form": form})


@router.post("/bins/{bin_id}/edit")
def bin_edit(
    request: Request, db: DbSession, admin: AdminUser, bin_id: int,
    name: Text = "", colour: Text = "#6c757d", description: OptionalText = "",
):
    bin_type = found(svc.get_bin_type(db, bin_id), "Bin type")
    try:
        svc.save_bin_type(db, bin_type, name=name, colour=colour, description=description)
    except ServiceError as e:
        ctx = {"bin_type": bin_type, "error": str(e), "form": {"name": name, "colour": colour, "description": description}}
        return render(request, "materials/bin_form.html", ctx, status_code=400)
    flash(request, "Bin type updated.")
    return _go("/materials/bins")


@router.post("/bins/{bin_id}/delete")
def bin_delete(request: Request, db: DbSession, admin: AdminUser, bin_id: int):
    bin_type = found(svc.get_bin_type(db, bin_id), "Bin type")
    try:
        svc.delete_bin_type(db, bin_type)
        flash(request, "Bin type deleted.", "info")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go("/materials/bins")


# ---------- Categories (admin) ----------


def _category_form(request, db, *, category=None, form=None, error=None, status_code=200):
    ctx = {"category": category, "form": form or {}, "error": error, "bin_types": svc.list_bin_types(db)}
    return render(request, "materials/form.html", ctx, status_code=status_code)


@router.get("/new")
def category_new_page(request: Request, db: DbSession, admin: AdminUser):
    return _category_form(request, db, form={"is_recyclable": True, "points_per_kg": "0"})


@router.post("/new")
def category_create(
    request: Request, db: DbSession, admin: AdminUser,
    name: Text = "", description: OptionalText = "", examples: OptionalText = "",
    is_recyclable: Annotated[bool, Form()] = False, points_per_kg: Text = "0",
    bin_type_id: OptionalText = "", steps: OptionalText = "",
):
    form = {"name": name, "description": description, "examples": examples, "is_recyclable": is_recyclable,
            "points_per_kg": points_per_kg, "bin_type_id": bin_type_id, "steps": steps}
    try:
        category = svc.save_category(db, None, **form)
    except ServiceError as e:
        return _category_form(request, db, form=form, error=str(e), status_code=400)
    flash(request, f"Material '{category.name}' added.")
    return _go(f"/materials/{category.id}")


@router.get("/{category_id}")
def category_detail(request: Request, db: DbSession, category_id: int):
    category = found(svc.get_category(db, category_id), "Material")
    return render(request, "materials/detail.html", {"category": category})


@router.get("/{category_id}/edit")
def category_edit_page(request: Request, db: DbSession, admin: AdminUser, category_id: int):
    c = found(svc.get_category(db, category_id), "Material")
    form = {
        "name": c.name, "description": c.description or "", "examples": c.examples or "",
        "is_recyclable": c.is_recyclable, "points_per_kg": c.points_per_kg, "bin_type_id": c.bin_type_id or "",
    }
    return _category_form(request, db, category=c, form=form)


@router.post("/{category_id}/edit")
def category_edit(
    request: Request, db: DbSession, admin: AdminUser, category_id: int,
    name: Text = "", description: OptionalText = "", examples: OptionalText = "",
    is_recyclable: Annotated[bool, Form()] = False, points_per_kg: Text = "0", bin_type_id: OptionalText = "",
):
    category = found(svc.get_category(db, category_id), "Material")
    form = {"name": name, "description": description, "examples": examples, "is_recyclable": is_recyclable,
            "points_per_kg": points_per_kg, "bin_type_id": bin_type_id}
    try:
        svc.save_category(db, category, **form)
    except ServiceError as e:
        return _category_form(request, db, category=category, form=form, error=str(e), status_code=400)
    flash(request, "Material updated.")
    return _go(f"/materials/{category.id}")


@router.post("/{category_id}/delete")
def category_delete(request: Request, db: DbSession, admin: AdminUser, category_id: int):
    category = found(svc.get_category(db, category_id), "Material")
    name = category.name
    svc.delete_category(db, category)
    flash(request, f"Material '{name}' deleted.", "info")
    return _go("/materials")


# ---------- Preparation steps (admin) ----------


def _step_action(request: Request, category_id: int, action) -> RedirectResponse:
    try:
        action()
        flash(request, "Preparation steps updated.")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go(f"/materials/{category_id}#steps")


@router.post("/{category_id}/steps")
def step_add(request: Request, db: DbSession, admin: AdminUser, category_id: int, instruction: Text = ""):
    category = found(svc.get_category(db, category_id), "Material")
    return _step_action(request, category_id, lambda: svc.add_step(db, category, instruction))


@router.post("/{category_id}/steps/{step_id}/edit")
def step_edit(request: Request, db: DbSession, admin: AdminUser, category_id: int, step_id: int,
              instruction: Text = ""):
    category = found(svc.get_category(db, category_id), "Material")
    return _step_action(request, category_id, lambda: svc.update_step(db, category, step_id, instruction))


@router.post("/{category_id}/steps/{step_id}/move")
def step_move(request: Request, db: DbSession, admin: AdminUser, category_id: int, step_id: int,
              direction: Text = "up"):
    category = found(svc.get_category(db, category_id), "Material")
    return _step_action(request, category_id, lambda: svc.move_step(db, category, step_id, direction))


@router.post("/{category_id}/steps/{step_id}/delete")
def step_delete(request: Request, db: DbSession, admin: AdminUser, category_id: int, step_id: int):
    category = found(svc.get_category(db, category_id), "Material")
    return _step_action(request, category_id, lambda: svc.delete_step(db, category, step_id))
