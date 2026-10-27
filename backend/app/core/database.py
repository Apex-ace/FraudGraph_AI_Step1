from functools import lru_cache

from sqlalchemy import create_engine, text

from app.core.config import settings


@lru_cache(maxsize=1)
def get_engine():
    if not settings.database_url or "YOUR_" in settings.database_url:
        raise ValueError("Set a real DATABASE_URL in backend/.env first")
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must point to PostgreSQL using psycopg")
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        connect_args={"sslmode": "require", "connect_timeout": 7},
    )


def test_database_connection() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar_one() == 1
