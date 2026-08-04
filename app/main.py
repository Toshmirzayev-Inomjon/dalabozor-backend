"""DalaBozor API — kirish nuqtasi."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import engine

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prod'da scheduler shu yerda ishga tushiriladi (Faza 4)
    if settings.scheduler_enabled:
        from app.jobs.scheduler import start_scheduler, shutdown_scheduler

        start_scheduler()
        yield
        shutdown_scheduler()
    else:
        yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # `allow_credentials=True` bilan `*` kombinatsiyasi brauzer tomonidan
    # rad etiladi. Frontend bir xil domen orqali ishlagani uchun wildcard
    # yetarli; prod'da aniq domenlar ro'yxati ishlatilsin.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(self), microphone=(), camera=()"
    )
    if settings.is_prod:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.get("/health", tags=["service"])
async def health():
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.env,
        "db": db_status,
    }
