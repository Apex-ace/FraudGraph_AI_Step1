"""SQLite-local by default, with optional legacy PostgreSQL support."""
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.core.config import backend_path, settings


@lru_cache(maxsize=1)
def get_engine():
    provider = settings.db_provider.lower()
    if provider == "sqlite":
        database_path = backend_path(settings.local_sqlite_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            "sqlite+pysqlite:///" + database_path.as_posix(),
            pool_pre_ping=True,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        # WAL allows readers and the simulator writer to coexist efficiently.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        return engine

    if provider != "postgres":
        raise ValueError("DB_PROVIDER must be sqlite or postgres")
    if not settings.database_url or "YOUR_" in settings.database_url:
        raise ValueError("Set DATABASE_URL only when DB_PROVIDER=postgres")
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must use postgresql+psycopg://")
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2,
                         connect_args={"sslmode": "require", "connect_timeout": 7})


def init_db():
    # Register ALL ORM models before create_all. Only local SQLite auto-creates
    # tables; existing Supabase installations continue using SQL migrations.
    from app.models.ledger import Base
    from app.models import alerts, local_user  # noqa: F401
    if settings.db_provider.lower() == "sqlite":
        Base.metadata.create_all(get_engine())


def test_database_connection() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar_one() == 1


def get_session():
    with Session(get_engine()) as session:
        yield session
