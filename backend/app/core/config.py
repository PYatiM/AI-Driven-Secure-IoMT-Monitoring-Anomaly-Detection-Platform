from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(
        default="AI-Driven Secure IoMT Monitoring Anomaly Detection Platform"
    )
    app_env: str = Field(default="development")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    api_v1_prefix: str = Field(default="/api/v1")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
