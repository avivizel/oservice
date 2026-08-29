from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import ROOT
from app.cos import restore_from_cos
from app.db import SessionLocal, init_db, persist_sqlite
from app.routers import agent, views
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
    persist_sqlite()
    yield
    persist_sqlite()


app = FastAPI(title="מענים", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
app.include_router(views.router)
app.include_router(agent.router)
