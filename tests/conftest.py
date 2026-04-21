from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session


TEST_DB_PATH = Path(".tmp/test_app.db")
ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _configure_test_environment() -> None:
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("APP_DEBUG", "false")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./.tmp/test_app.db")
    os.environ.setdefault("DB_ECHO", "false")
    os.environ.setdefault("TELEMETRY_QUEUE_ENABLED", "false")
    os.environ.setdefault("FIREWALL_ENABLED", "false")
    os.environ.setdefault("AUDIT_LOGGING_ENABLED", "false")
    os.environ.setdefault("SECURITY_EVENT_LOGGING_ENABLED", "false")
    os.environ.setdefault("HTTPS_ENFORCED", "false")
    os.environ.setdefault("AI_MODEL_ENABLED", "false")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-plus-chars")
    os.environ.setdefault(
        "DEVICE_TOKEN_SECRET_KEY",
        "test-device-token-secret-key-with-32-plus-chars",
    )
    os.environ.setdefault("DATA_ENCRYPTION_KEY", "test-data-encryption-secret-key-32-plus")


def _clear_runtime_caches() -> None:
    from backend.app.core.config import get_settings
    from backend.app.db.session import get_engine, get_session_factory
    from backend.app.security.encryption import get_fernet
    from backend.app.security.key_storage import get_key_storage
    from backend.app.services.anomaly_detection import (
        get_inference_pipeline,
        get_performance_monitor,
        get_prediction_logger,
    )

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_fernet.cache_clear()
    get_key_storage.cache_clear()
    get_inference_pipeline.cache_clear()
    get_prediction_logger.cache_clear()
    get_performance_monitor.cache_clear()


_configure_test_environment()
_clear_runtime_caches()

from backend.app.db.base import Base  # noqa: E402
from backend.app.db.session import get_engine, get_session_factory  # noqa: E402
from backend.app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def initialize_database() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def app(initialize_database):
    application = create_app()
    yield application


@pytest.fixture(autouse=True)
def clean_database(initialize_database) -> None:
    session = get_session_factory()()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.commit()
    finally:
        session.close()


@pytest.fixture
def db_session() -> Session:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
