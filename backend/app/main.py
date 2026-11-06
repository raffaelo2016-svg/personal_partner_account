import logging
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.admin_access import router as admin_access_router
from app.api.admin_bitrix_attention import router as admin_bitrix_attention_router
from app.api.admin_chat import router as admin_chat_router
from app.api.admin_clients import router as admin_clients_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.admin_finance import router as admin_finance_router
from app.api.admin_partners import router as admin_partners_router
from app.api.admin_settings import router as admin_settings_router
from app.api.auth import router as auth_router
from app.api.bitrix24_integration import router as bitrix24_integration_router
from app.api.chat import router as chat_router
from app.api.clients import router as clients_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.finance import router as finance_router
from app.api.news import admin_router as admin_news_router
from app.api.news import router as news_router
from app.api.notifications import router as notifications_router
from app.api.partner_settings import router as partner_settings_router
from app.api.tasks import router as tasks_router
from app.api.training import router as training_router
from app.api.webhooks import router as webhooks_router
from app.api.ws_chat import router as ws_chat_router
from app.config import settings
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.database import engine

# ── Logging setup ─────────────────────────────────────────────────

_log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

_SENSITIVE_QUERY_KEYS = {"email", "phone", "password", "token", "secret", "inn", "passport", "snils", "search"}


def _sanitize_query(query: str) -> str:
    """Redact sensitive query-param values to avoid PII in logs."""
    if not query:
        return ""
    from urllib.parse import parse_qsl, urlencode

    try:
        pairs = parse_qsl(query, keep_blank_values=True)
    except Exception:
        return "[unparseable]"
    sanitized = [(k, "***REDACTED***" if k.lower() in _SENSITIVE_QUERY_KEYS else v) for k, v in pairs]
    return urlencode(sanitized)


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level),
)

# Suppress default uvicorn access log to avoid duplication
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = structlog.get_logger()


# ── App lifecycle ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.yookassa_service import init_yookassa

    init_yookassa()
    logger.info("application_startup")
    yield
    await engine.dispose()
    logger.info("application_shutdown")


_is_prod = settings.ENVIRONMENT in ("production", "staging")

app = FastAPI(
    title="URITECH Partner Cabinet API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
    # DDoS-Guard перед nginx нормализует URL и может добавлять trailing
    # slash. Если redirect_slashes=True, Starlette ответит 307 на URL без
    # слеша → браузер снова follow'ит к /path/ → CDN снова 301 на /path → …
    # → ERR_TOO_MANY_REDIRECTS ("Network Error" в SPA).
    # Гасим встроенный редирект и стрипаем slash сами middleware'ой ниже.
    redirect_slashes=False,
)

if _is_prod:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── Trailing-slash normalization ──────────────────────────────────
# DDoS-Guard (CDN перед nginx) добавляет trailing slash к путям типа
# /api/v1/files → /api/v1/files/. Роуты в приложении объявлены без
# слеша. Сняли redirect_slashes=False, а здесь мутируем scope['path']
# так, что Starlette-роутер находит endpoint по оригинальному пути.
# Корневой '/' не трогаем.


@app.middleware("http")
async def strip_trailing_slash(request: Request, call_next):
    path = request.scope.get("path", "")
    if len(path) > 1 and path.endswith("/"):
        request.scope["path"] = path.rstrip("/")
        # raw_path держит байты и тоже участвует в роутинге starlette'а
        raw_path = request.scope.get("raw_path")
        if isinstance(raw_path, bytes):
            request.scope["raw_path"] = raw_path.rstrip(b"/") or b"/"
    return await call_next(request)


# ── Request logging middleware ────────────────────────────────────


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    method = request.method
    path = request.url.path
    query = _sanitize_query(str(request.url.query)) if request.url.query else ""
    client_ip = request.client.host if request.client else "unknown"

    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.error(
            "request_error",
            method=method,
            path=path,
            query=query,
            client_ip=client_ip,
            duration_ms=duration_ms,
        )
        raise

    duration_ms = round((time.perf_counter() - start) * 1000)
    status = response.status_code
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    log_kw = {
        "method": method,
        "path": path,
        "query": query,
        "status": status,
        "duration_ms": duration_ms,
        "client_ip": client_ip,
    }

    if status >= 500:
        logger.error("request_completed", **log_kw)
    elif status >= 400:
        logger.warning("request_completed", **log_kw)
    else:
        logger.info("request_completed", **log_kw)

    return response


# ── Exception handlers ────────────────────────────────────────────


def _cors_headers(request: Request) -> dict[str, str]:
    """CORS-заголовки для exception-ответов.

    Starlette's CORSMiddleware при allow_credentials=True не оборачивает
    ответы, которые возвращают exception-handler'ы — браузер блокирует
    401/403/422/429/500 и axios видит error.response=undefined.
    """
    origin = request.headers.get("origin", "")
    if origin in settings.cors_origins_list:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def _clean_pydantic_msg(raw: str) -> str:
    """Снимает автоматические префиксы Pydantic v2 ('Value error, ', 'Assertion error, ')."""
    for prefix in ("Value error, ", "Assertion error, "):
        if raw.startswith(prefix):
            return raw[len(prefix) :]
    return raw


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Pydantic v2 в err["ctx"] кладёт исходный ValueError — JSON его не сериализует,
    # поэтому возвращаем только type/loc/msg.
    clean = [
        {
            "type": err.get("type", "value_error"),
            "loc": list(err.get("loc", [])),
            "msg": _clean_pydantic_msg(err.get("msg", "")),
        }
        for err in exc.errors()
    ]
    fields = [f"{' → '.join(str(p) for p in e['loc'])}: {e['msg']} (type={e['type']})" for e in clean]

    logger.warning(
        "validation_error",
        method=request.method,
        path=request.url.path,
        errors=fields,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": clean, "code": "VALIDATION_ERROR"},
        headers=_cors_headers(request),
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    method = getattr(request, "method", "WS")
    logger.warning(
        "app_exception",
        method=method,
        path=request.url.path,
        status=exc.status_code,
        code=exc.code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
        headers=_cors_headers(request),
    )


# ── Rate limiting ────────────────────────────────────────────────

app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(
        "rate_limit_exceeded",
        method=getattr(request, "method", "?"),
        path=request.url.path,
        detail=str(exc.detail),
    )
    headers = {"Retry-After": "60", **_cors_headers(request)}
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}", "code": "RATE_LIMIT_EXCEEDED"},
        headers=headers,
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]

# ── Routers ──────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api/v1")
app.include_router(bitrix24_integration_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(ws_chat_router)
app.include_router(clients_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(news_router, prefix="/api/v1")
app.include_router(admin_news_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(admin_partners_router, prefix="/api/v1")
app.include_router(admin_clients_router, prefix="/api/v1")
app.include_router(training_router, prefix="/api/v1")
app.include_router(admin_dashboard_router, prefix="/api/v1")
app.include_router(admin_finance_router, prefix="/api/v1")
app.include_router(admin_settings_router, prefix="/api/v1")
app.include_router(admin_access_router, prefix="/api/v1")
app.include_router(admin_chat_router, prefix="/api/v1")
app.include_router(admin_bitrix_attention_router, prefix="/api/v1")
app.include_router(partner_settings_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
async def health(deep: int = 0):
    if not deep:
        return {"status": "ok", "version": "0.1.0"}

    from sqlalchemy import text

    from app.core.redis import redis_client
    from app.services.s3_service import _get_s3

    checks: dict[str, str] = {}
    failed = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["db"] = f"fail: {e.__class__.__name__}"
        failed = True

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis"] = f"fail: {e.__class__.__name__}"
        failed = True

    try:
        _get_s3().head_bucket(Bucket=settings.S3_BUCKET)
        checks["s3"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["s3"] = f"fail: {e.__class__.__name__}"
        failed = True

    body = {"status": "fail" if failed else "ok", "version": "0.1.0", "checks": checks}
    return JSONResponse(status_code=503 if failed else 200, content=body)
