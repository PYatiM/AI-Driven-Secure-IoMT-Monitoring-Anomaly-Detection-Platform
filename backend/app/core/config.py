from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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
    api_validate_requests: bool = Field(default=True)
    api_enforce_json_content_type: bool = Field(default=True)
    api_max_request_body_bytes: int = Field(default=1048576, ge=1)
    audit_logging_enabled: bool = Field(default=True)
    https_enforced: bool = Field(default=False)
    https_redirect_status_code: int = Field(default=307)
    https_hsts_enabled: bool = Field(default=True)
    https_hsts_max_age: int = Field(default=31536000, ge=0)
    https_hsts_include_subdomains: bool = Field(default=True)
    https_hsts_preload: bool = Field(default=False)

    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = Field(default="iomt_platform")
    db_user: str = Field(default="postgres")
    db_password: str = Field(default="postgres")
    db_echo: bool = Field(default=False)
    database_url: str | None = Field(default=None)

    jwt_secret_key: str = Field(default="change-this-jwt-secret-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expires_minutes: int = Field(default=60, ge=1)
    device_token_secret_key: str = Field(
        default="change-this-device-token-secret-in-production"
    )
    device_token_algorithm: str = Field(default="HS256")
    device_token_expires_minutes: int = Field(default=15, ge=1)
    data_encryption_key: str = Field(
        default="change-this-data-encryption-key-in-production"
    )

    ai_model_enabled: bool = Field(default=False)
    ai_model_path: str | None = Field(default=None)
    ai_model_registry_path: str = Field(default="ai/artifacts/model_registry.json")
    ai_prediction_log_path: str = Field(default="ai/logs/model_predictions.jsonl")
    ai_monitoring_metrics_path: str = Field(
        default="ai/monitoring/model_performance.json"
    )
    intrusion_detection_enabled: bool = Field(default=True)
    intrusion_score_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    intrusion_anomaly_score_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    intrusion_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
