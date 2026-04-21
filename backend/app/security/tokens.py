from __future__ import annotations

from typing import Any

import jwt
from jwt import InvalidTokenError


def encode_jwt(payload: dict[str, Any], secret_key: str, algorithm: str = "HS256") -> str:
    return str(jwt.encode(payload, secret_key, algorithm=algorithm))


def decode_jwt(token: str, secret_key: str, algorithm: str = "HS256") -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[algorithm])
