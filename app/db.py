from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL
from app.models import Base

log = logging.getLogger("maaneim.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def checkpoint() -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()


def persist_sqlite() -> None:
    from app.config import COS_ENABLED
    from app.cos import persist_to_cos

    if not COS_ENABLED:
        return
    checkpoint()
    persist_to_cos()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate()
    from app.localities import seed_localities

    db = SessionLocal()
    try:
        seed_localities(db)
    finally:
        db.close()


def _migrate() -> None:
    extras = {
        "operator_type": "VARCHAR(40) DEFAULT ''",
        "operator_name": "VARCHAR(300) DEFAULT ''",
        "supervision_text": "TEXT DEFAULT ''",
        "service_types": "TEXT DEFAULT '[]'",
        "population": "TEXT DEFAULT '[]'",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(services)"))}
        for name, ddl in extras.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE services ADD COLUMN {name} {ddl}"))


@event.listens_for(Session, "after_commit")
def _after_commit(_session) -> None:
    try:
        persist_sqlite()
    except Exception:
        log.exception("Failed to persist SQLite to COS after commit")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
