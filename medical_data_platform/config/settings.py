"""
MedInsight Analytics Platform - Application Settings
Centralised configuration using pydantic-settings.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=BASE_DIR / ".env", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="vlad")
    password: str = Field(default="vlad123")
    name: str = Field(default="portfolio")

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class DataSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    seed: int = Field(default=42)
    num_doctors: int = Field(default=50)
    num_patients: int = Field(default=5000)
    num_appointments: int = Field(default=20000)
    start_date: str = Field(default="2023-01-01")
    end_date: str = Field(default="2024-12-31")
    batch_size: int = Field(default=1000)

    raw_dir: Path = Field(default=BASE_DIR / "data" / "raw")
    bronze_dir: Path = Field(default=BASE_DIR / "data" / "bronze")
    silver_dir: Path = Field(default=BASE_DIR / "data" / "silver")
    gold_dir: Path = Field(default=BASE_DIR / "data" / "gold")
    exports_dir: Path = Field(default=BASE_DIR / "data" / "exports")

    def ensure_dirs(self) -> None:
        for d in [self.raw_dir, self.bronze_dir, self.silver_dir, self.gold_dir, self.exports_dir]:
            d.mkdir(parents=True, exist_ok=True)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    dashboard_port: int = Field(default=8501)
    dashboard_host: str = Field(default="localhost")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()


class Settings:
    """Aggregated settings facade."""

    def __init__(self) -> None:
        self.db = DatabaseSettings()
        self.data = DataSettings()
        self.app = AppSettings()
        self.base_dir = BASE_DIR
        self.logs_dir = BASE_DIR / "logs"
        self.logs_dir.mkdir(exist_ok=True)

    def __repr__(self) -> str:
        return (
            f"Settings(env={self.app.app_env}, "
            f"db={self.db.host}:{self.db.port}/{self.db.name})"
        )


settings = Settings()
