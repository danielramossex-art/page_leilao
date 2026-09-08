from __future__ import annotations

from contextlib import contextmanager, closing
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BASE_DIR, get_settings


class Base(DeclarativeBase):
    pass


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        relative = url.replace("sqlite:///", "", 1)
        return "sqlite:///" + str((BASE_DIR / Path(relative)).resolve()).replace("\\", "/")
    return url


settings = get_settings()
engine = create_engine(
    _normalize_database_url(settings.database_url),
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    existing = {column["name"] for column in inspect(engine).get_columns("properties")}
    additions = {
        "institution": "VARCHAR(160)", "source_name": "VARCHAR(160)", "official_url": "TEXT",
        "bedrooms": "INTEGER", "parking_spaces": "INTEGER", "accepts_financing": "BOOLEAN",
        "opportunity_score": "INTEGER", "data_quality": "VARCHAR(40)", "verified_at": "TIMESTAMP",
        "source_updated_at": "TIMESTAMP", "ends_at": "TIMESTAMP", "is_favorite": "BOOLEAN DEFAULT FALSE NOT NULL",
    }
    missing = {key: value for key, value in additions.items() if key not in existing}
    if missing:
        if engine.dialect.name == "sqlite":
            import sqlite3
            from datetime import datetime
            backup_dir = BASE_DIR / "data" / "backups"
            backup_dir.mkdir(exist_ok=True)
            database_path = engine.url.database
            if database_path and database_path != ":memory:":
                with closing(sqlite3.connect(database_path)) as source, closing(sqlite3.connect(
                    str(backup_dir / f"before_review_{datetime.now():%Y%m%d_%H%M%S_%f}.db")
                )) as backup:
                    source.backup(backup)
        with engine.begin() as connection:
            for name, sql_type in missing.items():
                connection.execute(text(f"ALTER TABLE properties ADD COLUMN {name} {sql_type}"))
            if "data_quality" in missing:
                connection.execute(text("UPDATE properties SET data_quality = 'legacy'"))
