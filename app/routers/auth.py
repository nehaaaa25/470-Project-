"""CONTROLLER: login, register, logout."""
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.dependencies import CurrentUser, DbSession
from app.models import Role
from app.services import auth_service
from app.services.auth_service import RESIDENT_TYPES, SELF_REGISTER_ROLES, RegistrationError
from app.templating import flash, render

router = APIRouter(tags=["Auth"])


def _safe_next(url: str | None) -> str:
    """Only allow redirects inside this site (stops open-redirect tricks)."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return "/dashboard"


@router.get("/login")
def login_page(request: Request, user: CurrentUser, next: str = "/dashboard"):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/login.html", {"next": _safe_next(next)})


@router.post("/login")
def login(
    request: Request,
    db: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/dashboard",
):
    user = auth_service.authenticate(db, email, password)
    if user is None:
        ctx = {"next": _safe_next(next), "email": email, "error": "Wrong email or password."}
        return render(request, "auth/login.html", ctx, status_code=400)
    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, f"Welcome back, {user.name}!")
    return RedirectResponse(_safe_next(next), status_code=303)


@router.get("/register")
def register_page(request: Request, user: CurrentUser):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    ctx = {"roles": SELF_REGISTER_ROLES, "resident_types": RESIDENT_TYPES, "form": {"role": Role.RESIDENT.value}}
    return render(request, "auth/register.html", ctx)


@router.post("/register")
def register(
    request: Request,
    db: DbSession,
    role: Annotated[str, Form()],
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    phone: Annotated[str, Form()] = "",
    address: Annotated[str, Form()] = "",
    resident_type: Annotated[str, Form()] = "household",
    company_name: Annotated[str, Form()] = "",
    trade_license_no: Annotated[str, Form()] = "",
    organization_name: Annotated[str, Form()] = "",
    contact_person: Annotated[str, Form()] = "",
):
    form = {
        "role": role, "name": name, "email": email, "phone": phone,
        "address": address, "resident_type": resident_type,
        "company_name": company_name, "trade_license_no": trade_license_no,
        "organization_name": organization_name, "contact_person": contact_person,
    }
    try:
        if role not in SELF_REGISTER_ROLES:
            raise RegistrationError("Please choose a valid account type.")
        if password != confirm_password:
            raise RegistrationError("The two passwords do not match.")
        auth_service.register_user(
            db, role=role, name=name, email=email, password=password, phone=phone, profile=form,
        )
    except RegistrationError as e:
        ctx = {"roles": SELF_REGISTER_ROLES, "resident_types": RESIDENT_TYPES, "form": form, "error": str(e)}
        return render(request, "auth/register.html", ctx, status_code=400)

    flash(request, "Account created. Please log in.")
    return RedirectResponse("/login", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "You have been logged out.", "info")
    return RedirectResponse("/", status_code=303)
