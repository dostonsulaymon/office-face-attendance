from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Database / cache
    database_url: str = "postgresql+asyncpg://attendance:attendance@postgres:5432/attendance"
    redis_url: str = "redis://redis:6379/0"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "change-me-admin-password"

    # CompreFace
    compreface_url: str = "http://compreface-ui:80"
    compreface_recognition_api_key: str = ""

    # Liveness
    liveness_url: str = "http://liveness:8902"
    liveness_threshold: float = 0.85

    # Business rules (runtime-adjustable defaults)
    recognition_confidence_threshold: float = 0.90
    cooldown_seconds: int = 30
    workday_cutoff_hour: int = 23
    image_retention_days: int = 14

    # Storage
    data_dir: str = "/data"
    image_encryption_key: str = ""

    # Networking
    dashboard_origin: str = "http://localhost:5173"
    api_port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
