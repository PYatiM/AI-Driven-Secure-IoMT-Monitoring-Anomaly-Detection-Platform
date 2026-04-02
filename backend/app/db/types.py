from __future__ import annotations

import json
from typing import Any

from sqlalchemy.types import Text, TypeDecorator

from backend.app.security.encryption import decrypt_text, encrypt_text


class EncryptedTextType(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("EncryptedTextType only accepts string values.")
        return encrypt_text(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt_text(value)


class EncryptedJSONType(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        serialized = json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
        return encrypt_text(serialized)

    def process_result_value(self, value: str | None, dialect) -> Any:
        if value is None:
            return None
        decrypted = decrypt_text(value)
        return json.loads(decrypted)
