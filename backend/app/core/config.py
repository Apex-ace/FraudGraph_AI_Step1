from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    database_url: str = ""
    frontend_origin: str = "http://localhost:5173"
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
