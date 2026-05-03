import os
from collections.abc import Generator

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


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _upgrade_reconciliations_table()


def _upgrade_reconciliations_table() -> None:
    inspector = inspect(engine)
    if "reconciliations" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("reconciliations")}
    needed_columns = {
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
        for column_name, column_definition in needed_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE reconciliations ADD COLUMN {column_name} {column_definition}"))
