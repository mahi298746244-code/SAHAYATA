"""SAHAYATA FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("sahayata.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if settings.is_sqlite:
        from app.db.session import create_all

        create_all()
        log.info("sqlite dev database ensured (production must use Alembic)")
    elif settings.is_postgres:
        # PostGIS extension + generated geom columns are handled by Alembic;
        # here we only make sure the extension exists when we may create it.
        from sqlalchemy import text

        from app.db.session import engine

        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            log.info("postgis extension verified")
        except Exception:
            log.warning("could not ensure postgis extension (needs superuser or pre-created DB)")

    if not settings.SECRET_KEY and settings.ENVIRONMENT == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    if not settings.SECRET_KEY:
        log.warning("SECRET_KEY not set – using INSECURE dev default; do NOT use in production")
        settings.SECRET_KEY = "dev-insecure-secret-key-change-me"
    yield


app = FastAPI(
    title="SAHAYATA API",
    description="Smart Citizen Support Platform – report civic issues, "
                "AI-assisted triage, clustering, priority and verification.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- HTTP layer -------------------------------------------------------------
app.add_middleware(GZipMiddleware, minimum_size=1024)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        csp = "default-src 'none'" if not request.url.path.startswith(("/docs", "/openapi")) else ""
        if csp:
            response.headers.setdefault("Content-Security-Policy", csp)
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- rate limiting -----------------------------------------------------------
from slowapi import Limiter  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests – please slow down.", "code": "rate_limited"},
    )


# --- consistent error envelope ----------------------------------------------
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        self.message = message
        self.status_code = status_code
        self.code = code


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "code": "validation_error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    message = "Internal server error" if settings.ENVIRONMENT == "production" else f"Internal error: {exc}"
    return JSONResponse(status_code=500, content={"detail": message, "code": "internal_error"})


app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "docs": "/docs"}
