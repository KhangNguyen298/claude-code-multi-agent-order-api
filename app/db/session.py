"""Engine, session factory, Base and the get_db dependency."""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


def enable_sqlite_fk(dbapi_connection, _record) -> None:
    """SQLite ignores foreign keys unless this PRAGMA is set per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


if _is_sqlite:
    # Registered on the Engine class so test engines created elsewhere get it too.
    event.listen(Engine, "connect", enable_sqlite_fk)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request. Services own commit/rollback."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind: Engine | None = None) -> None:
    """Create all tables (imports models so they are registered on Base)."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=bind or engine)
