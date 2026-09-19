from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

connect_args = (
    {"check_same_thread": False, "timeout": 30} if settings.is_sqlite else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Convenience for sqlite dev quickstart; production uses Alembic."""
    import app.models  # noqa: F401  ensure models are registered

    Base.metadata.create_all(bind=engine)
