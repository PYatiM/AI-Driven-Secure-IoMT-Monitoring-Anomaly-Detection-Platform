from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
USER_ACCESS_TOKEN_TYPE = "access"
DEVICE_ACCESS_TOKEN_TYPE = "device_access"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
    token_type: str = USER_ACCESS_TOKEN_TYPE,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return str(jwt.encode(payload, secret_key, algorithm=algorithm))


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str,
    expected_type: str = USER_ACCESS_TOKEN_TYPE,
) -> dict:
    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unsupported token type.")
    return payload


def create_device_access_token(
    device_id: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
) -> str:
    return create_access_token(
        subject=device_id,
        secret_key=secret_key,
        algorithm=algorithm,
        expires_minutes=expires_minutes,
        token_type=DEVICE_ACCESS_TOKEN_TYPE,
    )


def decode_device_access_token(token: str, secret_key: str, algorithm: str) -> dict:
    return decode_access_token(
        token=token,
        secret_key=secret_key,
        algorithm=algorithm,
        expected_type=DEVICE_ACCESS_TOKEN_TYPE,
    )
