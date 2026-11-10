"""Feature #20: Sponsor & Reward Commitment Management (owner: Rifa)

MVC files for this feature:
    Model      -> app/models/reward.py             Reward, RewardCommitment (Sponsor is in user.py)
    Service    -> app/services/reward_service.py   rules (end date after start date, stock never negative, ...)
    Controller -> this file                        URLs under /sponsors
    View       -> app/templates/sponsors/          HTML pages

Administrators manage everything. A sponsor can open only their own page (read-only).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.dependencies import AdminUser, DbSession, found, require_roles
from app.models import RewardStatus, Role, User
from app.services import reward_service as svc
from app.services.validation import ServiceError
from app.templating import flash, render

router = APIRouter(
    prefix="/sponsors",
    tags=["#20 Sponsors"],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR, Role.SPONSOR))],
)

Text = Annotated[str, Form()]
Checkbox = Annotated[bool, Form()]
AdminOrSponsor = Annotated[User, Depends(require_roles(Role.ADMINISTRATOR, Role.SPONSOR))]


def _go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _load_sponsor(db, sponsor_id: int, user: User):
    sponsor = found(svc.get_sponsor(db, sponsor_id), "Sponsor")
    if user.role != Role.ADMINISTRATOR and user.id != sponsor.id:
        raise HTTPException(status_code=403, detail="You can only view your own sponsor page.")
    return sponsor


def _load_reward(db, sponsor_id: int, reward_id: int):
    reward = found(svc.get_reward(db, reward_id), "Reward")
    if reward.sponsor_id != sponsor_id:
        found(None, "Reward")
    return reward


@router.get("")
def sponsors_index(request: Request, db: DbSession, user: AdminOrSponsor):
    if user.role == Role.SPONSOR:
        return _go(f"/sponsors/{user.id}")
    sponsors = svc.list_sponsors(db)
    rows = [(s, svc.sponsor_totals(s)) for s in sponsors]
    return render(request, "sponsors/index.html", {"rows": rows})


# ---------- Sponsors ----------


@router.get("/new")
def sponsor_new_page(request: Request, admin: AdminUser):
    return render(request, "sponsors/sponsor_new.html", {"form": {}})


@router.post("/new")
def sponsor_create(
    request: Request, db: DbSession, admin: AdminUser, organization_name: Text = "", contact_person: Text = "",
    name: Text = "", email: Text = "", phone: Text = "", password: Text = "", confirm_password: Text = "",
):
    form = {"organization_name": organization_name, "contact_person": contact_person, "name": name,
            "email": email, "phone": phone}
    try:
        sponsor = svc.register_sponsor(db, password=password, confirm_password=confirm_password, **form)
    except ServiceError as e:
        return render(request, "sponsors/sponsor_new.html", {"form": form, "error": str(e)}, status_code=400)
    flash(request, f"Sponsor '{sponsor.organization_name}' registered. They can log in with {sponsor.email}.")
    return _go(f"/sponsors/{sponsor.id}")


@router.get("/{sponsor_id}")
def sponsor_detail(request: Request, db: DbSession, user: AdminOrSponsor, sponsor_id: int):
    sponsor = _load_sponsor(db, sponsor_id, user)
    ctx = {"sponsor": sponsor, "totals": svc.sponsor_totals(sponsor), "can_manage": user.role == Role.ADMINISTRATOR}
    return render(request, "sponsors/detail.html", ctx)


@router.get("/{sponsor_id}/edit")
def sponsor_edit_page(request: Request, db: DbSession, admin: AdminUser, sponsor_id: int):
    s = found(svc.get_sponsor(db, sponsor_id), "Sponsor")
    form = {"organization_name": s.organization_name, "contact_person": s.contact_person or "", "name": s.name,
            "phone": s.phone or "", "is_active": s.is_active}
    return render(request, "sponsors/sponsor_edit.html", {"sponsor": s, "form": form})


@router.post("/{sponsor_id}/edit")
def sponsor_edit(
    request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, organization_name: Text = "",
    contact_person: Text = "", name: Text = "", phone: Text = "", is_active: Checkbox = False,
):
    sponsor = found(svc.get_sponsor(db, sponsor_id), "Sponsor")
    form = {"organization_name": organization_name, "contact_person": contact_person, "name": name,
            "phone": phone, "is_active": is_active}
    try:
        svc.update_sponsor(db, sponsor, **form)
    except ServiceError as e:
        ctx = {"sponsor": sponsor, "form": form, "error": str(e)}
        return render(request, "sponsors/sponsor_edit.html", ctx, status_code=400)
    flash(request, "Sponsor updated.")
    return _go(f"/sponsors/{sponsor.id}")


# ---------- Rewards ----------


def _reward_form(request, sponsor, *, reward=None, form=None, error=None, status_code=200):
    ctx = {"sponsor": sponsor, "reward": reward, "form": form or {}, "error": error, "statuses": list(RewardStatus)}
    return render(request, "sponsors/reward_form.html", ctx, status_code=status_code)


@router.get("/{sponsor_id}/rewards/new")
def reward_new_page(request: Request, db: DbSession, admin: AdminUser, sponsor_id: int):
    sponsor = found(svc.get_sponsor(db, sponsor_id), "Sponsor")
    return _reward_form(request, sponsor, form={"status": RewardStatus.ACTIVE.value})


@router.post("/{sponsor_id}/rewards/new")
def reward_create(
    request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, name: Text = "", description: Text = "",
    points_cost: Text = "", status: Text = "active",
):
    sponsor = found(svc.get_sponsor(db, sponsor_id), "Sponsor")
    form = {"name": name, "description": description, "points_cost": points_cost, "status": status}
    try:
        reward = svc.save_reward(db, sponsor, None, **form)
    except ServiceError as e:
        return _reward_form(request, sponsor, form=form, error=str(e), status_code=400)
    flash(request, f"Reward '{reward.name}' added. Now add a commitment so it has stock.")
    return _go(f"/sponsors/{sponsor.id}#reward-{reward.id}")


@router.get("/{sponsor_id}/rewards/{reward_id}/edit")
def reward_edit_page(request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, reward_id: int):
    reward = _load_reward(db, sponsor_id, reward_id)
    form = {"name": reward.name, "description": reward.description or "", "points_cost": reward.points_cost,
            "status": reward.status}
    return _reward_form(request, reward.sponsor, reward=reward, form=form)


@router.post("/{sponsor_id}/rewards/{reward_id}/edit")
def reward_edit(
    request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, reward_id: int, name: Text = "",
    description: Text = "", points_cost: Text = "", status: Text = "active",
):
    reward = _load_reward(db, sponsor_id, reward_id)
    form = {"name": name, "description": description, "points_cost": points_cost, "status": status}
    try:
        svc.save_reward(db, reward.sponsor, reward, **form)
    except ServiceError as e:
        return _reward_form(request, reward.sponsor, reward=reward, form=form, error=str(e), status_code=400)
    flash(request, "Reward updated.")
    return _go(f"/sponsors/{sponsor_id}#reward-{reward.id}")


@router.post("/{sponsor_id}/rewards/{reward_id}/delete")
def reward_delete(request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, reward_id: int):
    reward = _load_reward(db, sponsor_id, reward_id)
    name = reward.name
    svc.delete_reward(db, reward)
    flash(request, f"Reward '{name}' and its commitments deleted.", "info")
    return _go(f"/sponsors/{sponsor_id}")


# ---------- Commitments ----------


@router.post("/{sponsor_id}/rewards/{reward_id}/commitments")
def commitment_add(
    request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, reward_id: int, quantity: Text = "",
    valid_from: Text = "", valid_until: Text = "", note: Text = "",
):
    reward = _load_reward(db, sponsor_id, reward_id)
    try:
        c = svc.add_commitment(db, reward, quantity=quantity, valid_from=valid_from, valid_until=valid_until, note=note)
        flash(request, f"Commitment of {c.quantity} added to '{reward.name}'.")
    except ServiceError as e:
        flash(request, f"Could not add the commitment to '{reward.name}': {e}", "danger")
    return _go(f"/sponsors/{sponsor_id}#reward-{reward.id}")


@router.post("/{sponsor_id}/rewards/{reward_id}/commitments/{commitment_id}/delete")
def commitment_delete(
    request: Request, db: DbSession, admin: AdminUser, sponsor_id: int, reward_id: int, commitment_id: int,
):
    reward = _load_reward(db, sponsor_id, reward_id)
    try:
        svc.delete_commitment(db, reward, commitment_id)
        flash(request, "Commitment removed.", "info")
    except ServiceError as e:
        flash(request, str(e), "danger")
    return _go(f"/sponsors/{sponsor_id}#reward-{reward.id}")
