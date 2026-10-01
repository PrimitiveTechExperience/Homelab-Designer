from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://homelab:homelab@localhost:5432/homelab"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    verification_token_expire_hours: int = 24

    # Retailer ingestion (worker). Best Buy's official Products API; get a key at
    # https://developer.bestbuy.com/.
    bestbuy_api_key: str = ""

    # Where verification links point (the frontend route that calls /api/auth/verify-email).
    frontend_url: str = "http://localhost:5173"

    # "console" logs emails instead of sending them (local dev); "smtp" sends for real.
    email_backend: str = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "Homelab Parts Finder <no-reply@localhost>"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
