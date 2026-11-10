"""Shared FastAPI dependencies: database session, current user, role checks.

Use them in a controller like this:

    @router.get("/something")
    def page(request: Request, db: DbSession, user: LoggedInUser): ...

    router = APIRouter(dependencies=[Depends(require_roles(Role.MANAGER))])
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User

DbSession = Annotated[Session, Depends(get_db)]


class LoginRequired(Exception):
    """Raised when a page needs login; main.py turns it into a redirect to /login."""


def load_current_user(request: Request, db: DbSession) -> None:
    """Runs on every request (registered in main.py). Puts the user on request.state.user."""
    request.state.user = None
    user_id = request.session.get("user_id")
    if user_id is None:
        return
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.pop("user_id", None)
    else:
        request.state.user = user


def get_current_user(request: Request) -> User | None:
    return getattr(request.state, "user", None)


def require_login(request: Request) -> User:
    user = get_current_user(request)
    if user is None:
        raise LoginRequired()
    return user


def require_roles(*roles: Role):
    """Only let users with one of these roles through (others get a 403 page)."""
    allowed = {str(r) for r in roles}

    def checker(user: Annotated[User, Depends(require_login)]) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have access to this page.")
        return user

    return checker


def found(obj, what: str = "Page"):
    """Return obj, or show the 404 page if it is None (e.g. a wrong id in the URL)."""
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{what} not found.")
    return obj


CurrentUser = Annotated[User | None, Depends(get_current_user)]
LoggedInUser = Annotated[User, Depends(require_login)]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))]
StaffUser = Annotated[User, Depends(require_roles(Role.MANAGER, Role.ADMINISTRATOR))]
