"""FastAPI application entry point."""
import os

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from urllib.parse import urlparse
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.api.v1 import (
    auth,
    connections,
    extras,
    groups,
    interactions,
    media,
    moderation,
    notifications,
    posts,
    profile,
    search,
)
from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.db.database import Base, SessionLocal, engine
import backend.app.models  # noqa: F401 - register all ORM models with Base.metadata

logger = logging.getLogger("campusconnect")

APP_DIR = Path(__file__).resolve().parent          # backend/app/
STATIC_DIR = APP_DIR / "static"                    # backend/app/static/
PAGES_DIR = APP_DIR / "pages"                      # backend/app/pages/

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/password-reset/request",
    "/api/v1/auth/password-reset/confirm",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_settings()
    if "sqlite" in settings.DATABASE_URL and ":memory:" not in settings.DATABASE_URL:
        db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
        parent = Path(db_path).parent
        if str(parent) and str(parent) != ".":
            os.makedirs(parent, exist_ok=True)
    # In production, schema is managed strictly by Alembic migrations
    if settings.ENV != "production":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="CampusHive",
    version="1.3.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url="/redoc" if settings.ENV != "production" else None,
)


@app.middleware("http")
async def security_and_csrf_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]

    # CSRF & Origin/Referer protection for cookie-authenticated state-changing requests
    if (
        request.method in STATE_CHANGING_METHODS
        and request.url.path.startswith("/api/")
        and request.url.path not in CSRF_EXEMPT_PATHS
    ):
        session_cookie = request.cookies.get("session_token")
        if session_cookie:
            # Origin / Referer check when browser sends them
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            expected_host = request.headers.get("host", "")
            allowed_origin = settings.ALLOWED_ORIGIN

            if origin:
                parsed = urlparse(origin)
                origin_base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                if allowed_origin and origin_base != allowed_origin and parsed.netloc != expected_host:
                    return JSONResponse(
                        status_code=403,
                        content={"code": "csrf_origin_mismatch", "message": "Origin check failed", "request_id": request_id},
                    )
                if not allowed_origin and expected_host and parsed.netloc != expected_host:
                    return JSONResponse(
                        status_code=403,
                        content={"code": "csrf_origin_mismatch", "message": "Origin check failed", "request_id": request_id},
                    )
            elif referer:
                parsed = urlparse(referer)
                if expected_host and parsed.netloc != expected_host:
                    return JSONResponse(
                        status_code=403,
                        content={"code": "csrf_origin_mismatch", "message": "Referer check failed", "request_id": request_id},
                    )

            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("x-csrf-token")
            if csrf_cookie and csrf_header != csrf_cookie:
                return JSONResponse(
                    status_code=403,
                    content={"code": "csrf_invalid", "message": "Invalid or missing CSRF token", "request_id": request_id},
                )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include search before profile so /users/search is not captured by /users/{username}
app.include_router(auth.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(connections.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(interactions.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(extras.router, prefix="/api/v1")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})


def _serve_page(filename: str):
    candidate = PAGES_DIR / filename
    if candidate.is_file():
        return FileResponse(str(candidate))
    return JSONResponse(
        status_code=404,
        content={"code": "not_found", "message": f"Page '{filename}' not found"},
    )


@app.get("/")
def index_page():
    return _serve_page("landing.html")


@app.get("/login")
def login_page():
    return _serve_page("login.html")


@app.get("/register")
def register_page():
    return _serve_page("register.html")


@app.get("/home")
def home_page():
    return _serve_page("home.html")


@app.get("/feed")
def feed_page():
    return _serve_page("home.html")


@app.get("/connections")
def connections_page():
    return _serve_page("connections.html")


@app.get("/requests")
def requests_page():
    return _serve_page("requests.html")


@app.get("/discover")
def discover_page():
    return _serve_page("search.html")


@app.get("/search")
def search_page():
    return _serve_page("search.html")


@app.get("/my-profile")
def my_profile_page():
    return _serve_page("my_profile.html")


@app.get("/notifications")
def notifications_page():
    return _serve_page("notifications.html")


@app.get("/groups")
def groups_page():
    return _serve_page("groups.html")


@app.get("/settings")
def settings_page():
    return _serve_page("settings.html")


@app.get("/help")
def help_page():
    return _serve_page("help.html")


@app.get("/terms")
def terms_page():
    return _serve_page("terms.html")


@app.get("/privacy")
def privacy_page():
    return _serve_page("privacy.html")


@app.get("/profile/{username}")
def user_profile_page(username: str):
    return _serve_page("profile.html")


@app.get("/profile")
def profile_page():
    return _serve_page("profile.html")
