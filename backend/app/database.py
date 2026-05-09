import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./pesobooks.db")


DATABASE_URL = _database_url()
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Tables that existed before Alembic was introduced. If a database already has
# these but no `alembic_version`, it predates migrations and we patch any
# remaining gaps then stamp it at head instead of re-running the baseline.
_PRE_ALEMBIC_TABLES = {
    "users",
    "clients",
    "receipts",
    "receipt_data",
    "line_items",
    "bank_transactions",
    "reconciliations",
}


def _alembic_config():
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def _patch_pre_alembic_2307_columns() -> None:
    """The 2307 columns were added in production via a startup ALTER TABLE
    patch before Alembic existed. For databases predating that patch, fill the
    gap so the stamped baseline matches the actual schema.
    """
    inspector = inspect(engine)
    if "reconciliations" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("reconciliations")}
    needed = {
        "form_2307_status": "VARCHAR(20) NOT NULL DEFAULT 'missing'",
        "form_2307_file_path": "VARCHAR(500)",
        "form_2307_original_name": "VARCHAR(255)",
        "form_2307_mime_type": "VARCHAR(100)",
        "form_2307_uploaded_at": "DATETIME",
        "form_2307_requested_at": "DATETIME",
        "form_2307_received_at": "DATETIME",
        "form_2307_notes": "TEXT",
    }
    with engine.begin() as connection:
        for column_name, column_definition in needed.items():
            if column_name not in existing:
                connection.execute(
                    text(f"ALTER TABLE reconciliations ADD COLUMN {column_name} {column_definition}")
                )


def init_db() -> None:
    """Bring the database up to the latest Alembic revision.

    For pre-Alembic databases (created by the previous `Base.metadata.create_all`
    path), we backfill the 2307 columns and stamp the baseline as already
    applied so we don't try to recreate existing tables.
    """
    from alembic import command

    from app import models  # noqa: F401  (ensure models register on Base.metadata)

    cfg = _alembic_config()

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    has_version_table = "alembic_version" in existing
    looks_pre_alembic = (not has_version_table) and _PRE_ALEMBIC_TABLES.issubset(existing)

    if looks_pre_alembic:
        _patch_pre_alembic_2307_columns()
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
