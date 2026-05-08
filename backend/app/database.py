import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.schema import DDL


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://pesobooks:pesobooks@localhost:5432/pesobooks",
    )


DATABASE_URL = _database_url()
_IS_SQLITE = DATABASE_URL.startswith("sqlite")
CONNECT_ARGS = {"check_same_thread": False} if _IS_SQLITE else {}

_engine_kwargs = {"connect_args": CONNECT_ARGS}
if not _IS_SQLITE:
    _engine_kwargs.update(
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


_RECONCILIATION_COLUMNS: dict[str, str] = {
    "form_2307_status": "VARCHAR(20) NOT NULL DEFAULT 'missing'",
    "form_2307_file_path": "VARCHAR(500)",
    "form_2307_original_name": "VARCHAR(255)",
    "form_2307_mime_type": "VARCHAR(100)",
    "form_2307_uploaded_at": "TIMESTAMP",
    "form_2307_requested_at": "TIMESTAMP",
    "form_2307_received_at": "TIMESTAMP",
    "form_2307_notes": "TEXT",
}

_USER_COLUMNS: dict[str, str] = {
    "is_verified": "BOOLEAN NOT NULL DEFAULT FALSE",
    "verification_token": "VARCHAR(128)",
    "verification_token_expires_at": "TIMESTAMP",
    "verification_sent_at": "TIMESTAMP",
}

_ALLOWED_COLUMN_NAME = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _safe_identifier(name: str) -> str:
    if not name or any(ch not in _ALLOWED_COLUMN_NAME for ch in name):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _add_missing_columns(table: str, columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    table_safe = _safe_identifier(table)
    existing = {column["name"] for column in inspector.get_columns(table)}
    with engine.begin() as connection:
        for column_name, column_definition in columns.items():
            if column_name in existing:
                continue
            column_safe = _safe_identifier(column_name)
            connection.execute(
                DDL(f"ALTER TABLE {table_safe} ADD COLUMN {column_safe} {column_definition}")
            )


def _run_lightweight_migrations() -> None:
    _add_missing_columns("reconciliations", _RECONCILIATION_COLUMNS)
    _add_missing_columns("users", _USER_COLUMNS)
