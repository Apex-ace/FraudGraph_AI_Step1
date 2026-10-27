from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Local, offline-friendly defaults. Old Supabase .env credentials are ignored
    # unless these switches are explicitly changed back.
    db_provider: str = "sqlite"          # sqlite | postgres
    auth_mode: str = "local"             # local | supabase
    local_sqlite_path: str = "data/fraudgraph.db"
    local_auth_secret_file: str = "data/local_auth_secret.key"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    database_url: str = ""               # used only with DB_PROVIDER=postgres
    frontend_origin: str = "http://localhost:5173"
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def backend_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else BACKEND_ROOT / path
