from __future__ import annotations

import base64
from functools import lru_cache
from hashlib import sha256
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from backend.app.security.key_storage import get_data_encryption_key

ENCRYPTION_PREFIX: Final[str] = "enc::"


def _derive_fernet_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(sha256(secret.encode("utf-8")).digest())


@lru_cache
def get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key(get_data_encryption_key()))


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(ENCRYPTION_PREFIX)


def encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    if is_encrypted(value):
        return value

    token = get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTION_PREFIX}{token}"


def decrypt_text(
    value: str | None,
    *,
    allow_plaintext_fallback: bool = True,
) -> str | None:
    if value is None:
        return None
    if not is_encrypted(value):
        if allow_plaintext_fallback:
            return value
        raise ValueError("Stored value is not encrypted.")

    token = value[len(ENCRYPTION_PREFIX) :]
    try:
        return get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored value.") from exc
