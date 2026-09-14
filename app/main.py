from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import access_log
from app.admin_auth import BoundSessionMiddleware, ensure_session_secret, set_session_secret
from app.config import ROOT
from app.cos import restore_from_cos
from app.db import SessionLocal, init_db, persist_sqlite
from app.routers import admin, agent, views
from app.routers.admin import AdminAuthRequired
from app.seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    restored = restore_from_cos()
    init_db()
    if not restored:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    db = SessionLocal()
    try:
        set_session_secret(ensure_session_secret(db))
    finally:
        db.close()
    access_log.start_flusher()
    persist_sqlite()
    yield
    access_log.stop_flusher()
    persist_sqlite()


app = FastAPI(title="מענים", lifespan=lifespan)
app.add_middleware(BoundSessionMiddleware)
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
app.include_router(views.router)
app.include_router(agent.router)
app.include_router(admin.router)


@app.middleware("http")
async def record_access(request: Request, call_next):
    response = await call_next(request)
    access_log.record(request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(AdminAuthRequired)
async def admin_auth_redirect(_request: Request, _exc: AdminAuthRequired):
    return RedirectResponse("/admin/login", status_code=303)
