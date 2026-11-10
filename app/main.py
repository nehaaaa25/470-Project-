"""EcoWaste app entry point.

Run from the project folder:   uvicorn app.main:app --reload
Then open:                     http://127.0.0.1:8000

MVC map:
    Model      -> app/models/      (SQLAlchemy classes = MySQL tables)
    View       -> app/templates/   (Jinja2 + Bootstrap 5 HTML)
    Controller -> app/routers/     (URL handlers)
    Services   -> app/services/    (business rules the controllers call)
"""
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, settings
from app.dependencies import LoginRequired, load_current_user
from app.routers import auth, centres, materials, pages, special_items, sponsors, zones
from app.templating import render

app = FastAPI(title=settings.app_name, dependencies=[Depends(load_current_user)])

# Signed cookie that remembers who is logged in (8 hours).
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", max_age=8 * 60 * 60)

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")

for module in (pages, auth, materials, zones, centres, sponsors, special_items):
    app.include_router(module.router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    return RedirectResponse(f"/login?next={quote(request.url.path)}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def html_error_handler(request: Request, exc: StarletteHTTPException):
    # Browsers get a friendly page; API clients keep the normal JSON error.
    if exc.status_code in (403, 404) and "text/html" in request.headers.get("accept", ""):
        return render(request, f"errors/{exc.status_code}.html", {"detail": exc.detail}, status_code=exc.status_code)
    return await http_exception_handler(request, exc)
