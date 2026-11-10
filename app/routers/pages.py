"""CONTROLLER: home page, dashboard, health check."""
from fastapi import APIRouter, Request
from sqlalchemy import func, select, text

from app.dependencies import DbSession, LoggedInUser
from app.models import (
    CollectionCentre,
    Collector,
    MaterialCategory,
    Reward,
    Role,
    ServiceZone,
    SpecialItemRequest,
    Sponsor,
)
from app.services import special_item_service
from app.services.auth_service import FIELD_LABELS, PROFILE_FIELDS
from app.templating import render

router = APIRouter(tags=["Pages"])


@router.get("/")
def home(request: Request):
    return render(request, "home.html")


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def _stats(db, user) -> list[dict]:
    """Small numbers shown at the top of the dashboard, different for each role."""
    role = Role(user.role)
    if role in (Role.MANAGER, Role.ADMINISTRATOR):
        stats = [
            {"label": "Materials", "value": _count(db, MaterialCategory), "url": "/materials"},
            {"label": "Active centres", "value": _count(db, CollectionCentre, CollectionCentre.is_active.is_(True)),
             "url": "/centres"},
            {"label": "Service zones", "value": _count(db, ServiceZone), "url": "/zones"},
            {"label": "Collectors", "value": _count(db, Collector), "url": "/zones#collectors"},
            {"label": "Pending special requests",
             "value": _count(db, SpecialItemRequest, SpecialItemRequest.status == "pending"),
             "url": "/special-items?status=pending"},
        ]
        if role == Role.ADMINISTRATOR:
            stats.append({"label": "Sponsors", "value": _count(db, Sponsor), "url": "/sponsors"})
        return stats
    if role == Role.RESIDENT:
        counts = special_item_service.count_by_status(db, resident=user)
        return [
            {"label": "Pending requests", "value": counts["pending"], "url": "/special-items?status=pending"},
            {"label": "Approved requests", "value": counts["approved"], "url": "/special-items?status=approved"},
            {"label": "Materials in guide", "value": _count(db, MaterialCategory), "url": "/materials"},
        ]
    if role == Role.SPONSOR:
        return [
            {"label": "Your rewards", "value": _count(db, Reward, Reward.sponsor_id == user.id),
             "url": f"/sponsors/{user.id}"},
            {"label": "Units in stock",
             "value": db.scalar(select(func.coalesce(func.sum(Reward.stock_quantity), 0))
                                .where(Reward.sponsor_id == user.id)),
             "url": f"/sponsors/{user.id}"},
        ]
    if role == Role.COLLECTOR:
        return [{"label": "Your service zones", "value": len(user.zones), "url": None}]
    return []


@router.get("/dashboard")
def dashboard(request: Request, db: DbSession, user: LoggedInUser):
    profile = [
        (FIELD_LABELS[f], getattr(user, f)) for f in PROFILE_FIELDS[Role(user.role)]
    ]
    return render(request, "dashboard.html", {"profile": profile, "stats": _stats(db, user)})


@router.get("/health")
def health(db: DbSession):
    """Open http://127.0.0.1:8000/health to check the app can reach MySQL."""
    try:
        db.execute(text("SELECT 1"))
        return {"app": "ok", "database": "ok"}
    except Exception as e:  # noqa: BLE001 - report any DB problem
        return {"app": "ok", "database": "error", "detail": type(e).__name__ + ": " + str(e).splitlines()[0]}
