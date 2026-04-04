from __future__ import annotations

import base64
import json
import logging
import secrets
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

JWT_SECRET_KEY_NAME: Final[str] = "jwt_secret_key"
DEVICE_TOKEN_SECRET_KEY_NAME: Final[str] = "device_token_secret_key"
DATA_ENCRYPTION_KEY_NAME: Final[str] = "data_encryption_key"
DEFAULT_SECRET_PREFIXES: Final[tuple[str, ...]] = ("change-this-", "default-", "example-")


@dataclass(frozen=True)
class KeyStorageStatus:
    enabled: bool
    configured: bool
    path: str
    env_fallback_enabled: bool


class SecureKeyStorage:
    def __init__(self, path: str | Path, master_key: str) -> None:
        self.path = Path(path)
        self._fernet = Fernet(_derive_fernet_key(master_key))

    def _read_payload(self) -> dict[str, str]:
        if not self.path.exists():
            return {}

        encrypted_blob = self.path.read_bytes()
        if not encrypted_blob:
            return {}

        try:
            decrypted_json = self._fernet.decrypt(encrypted_blob).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt secure key storage file.") from exc

        payload = json.loads(decrypted_json)
        if not isinstance(payload, dict):
            raise ValueError("Secure key storage payload must be a JSON object.")

        return {str(key): str(value) for key, value in payload.items()}

    def _write_payload(self, payload: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        encrypted_blob = self._fernet.encrypt(serialized)
        self.path.write_bytes(encrypted_blob)

    def get_secret(self, name: str) -> str | None:
        return self._read_payload().get(name)

    def set_secret(self, name: str, value: str) -> None:
        normalized_name = name.strip()
        normalized_value = value.strip()
        if not normalized_name:
            raise ValueError("Secret name cannot be empty.")
        if not normalized_value:
            raise ValueError("Secret value cannot be empty.")

        payload = self._read_payload()
        payload[normalized_name] = normalized_value
        self._write_payload(payload)

    def delete_secret(self, name: str) -> None:
        payload = self._read_payload()
        if name in payload:
            payload.pop(name, None)
            self._write_payload(payload)

    def list_secret_names(self) -> list[str]:
        return sorted(self._read_payload().keys())


def _derive_fernet_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(sha256(secret.encode("utf-8")).digest())


def _is_placeholder_secret(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return any(normalized.startswith(prefix) for prefix in DEFAULT_SECRET_PREFIXES)


@lru_cache
def get_key_storage() -> SecureKeyStorage | None:
    settings = get_settings()
    if not settings.secure_key_storage_enabled:
        return None

    if not settings.key_storage_master_key:
        logger.warning(
            "Secure key storage is enabled, but KEY_STORAGE_MASTER_KEY is not configured. "
            "Falling back to environment secrets."
        )
        return None

    return SecureKeyStorage(
        path=settings.secure_key_storage_path,
        master_key=settings.key_storage_master_key,
    )


def get_key_storage_status() -> KeyStorageStatus:
    settings = get_settings()
    storage = get_key_storage()
    return KeyStorageStatus(
        enabled=settings.secure_key_storage_enabled,
        configured=storage is not None,
        path=settings.secure_key_storage_path,
        env_fallback_enabled=settings.key_storage_allow_env_fallback,
    )


def generate_secret_value(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def resolve_secret_value(name: str, fallback_value: str | None) -> str:
    settings = get_settings()
    storage = get_key_storage()
    if storage is not None:
        stored_value = storage.get_secret(name)
        if stored_value:
            return stored_value

    allow_fallback = (not settings.secure_key_storage_enabled) or settings.key_storage_allow_env_fallback
    if fallback_value and allow_fallback:
        return fallback_value

    raise ValueError(f"Required secret '{name}' is not configured.")


def get_jwt_secret_key() -> str:
    settings = get_settings()
    return resolve_secret_value(JWT_SECRET_KEY_NAME, settings.jwt_secret_key)


def get_device_token_secret_key() -> str:
    settings = get_settings()
    return resolve_secret_value(
        DEVICE_TOKEN_SECRET_KEY_NAME,
        settings.device_token_secret_key,
    )


def get_data_encryption_key() -> str:
    settings = get_settings()
    return resolve_secret_value(DATA_ENCRYPTION_KEY_NAME, settings.data_encryption_key)


def build_bootstrap_secret_map() -> dict[str, str]:
    settings = get_settings()
    secret_map = {
        JWT_SECRET_KEY_NAME: settings.jwt_secret_key,
        DEVICE_TOKEN_SECRET_KEY_NAME: settings.device_token_secret_key,
        DATA_ENCRYPTION_KEY_NAME: settings.data_encryption_key,
    }
    return {
        name: (generate_secret_value() if _is_placeholder_secret(value) else str(value).strip())
        for name, value in secret_map.items()
    }

