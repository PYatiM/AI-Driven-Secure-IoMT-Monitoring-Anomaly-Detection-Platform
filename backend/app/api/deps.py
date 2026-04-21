from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import AuditActorType, Device, DeviceStatus, User, UserRole
from backend.app.db.session import get_db
from backend.app.security.api_keys import build_api_key_lookup
from backend.app.security.auth import decode_access_token, decode_device_access_token
from backend.app.security.key_storage import get_device_token_secret_key, get_jwt_secret_key
from backend.app.security.tokens import InvalidTokenError
from backend.app.services.security_events import (
    SecurityEventCategory,
    SecurityEventOutcome,
    SecurityEventSeverity,
    log_security_event,
)

UNAUTHORIZED_DEVICE_API_KEY_MESSAGE = "Invalid or missing device API key."
UNAUTHORIZED_DEVICE_TOKEN_MESSAGE = "Invalid or missing device bearer token."
UNAUTHORIZED_USER_MESSAGE = "Invalid or missing bearer token."


@dataclass
class AuthenticationError(Exception):
    status_code: int
    detail: str
    headers: dict[str, str] | None = None


def _touch_device_authentication(device: Device, db: Session) -> Device:
    device.last_authenticated_at = datetime.now(timezone.utc)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def authenticate_device_api_key(db: Session, api_key: str | None) -> Device:
    if not api_key:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_API_KEY_MESSAGE,
        )

    api_key_prefix, api_key_hash = build_api_key_lookup(api_key)
    device = db.scalar(
        select(Device).where(
            Device.api_key_prefix == api_key_prefix,
            Device.api_key_hash == api_key_hash,
            Device.status == DeviceStatus.ACTIVE,
        )
    )
    if device is None:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_API_KEY_MESSAGE,
        )

    return _touch_device_authentication(device, db)


def _extract_bearer_token(
    authorization: str | None,
    *,
    unauthorized_message: str,
) -> str:
    if not authorization:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=unauthorized_message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=unauthorized_message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def authenticate_device_bearer_token(db: Session, authorization: str | None) -> Device:
    token = _extract_bearer_token(
        authorization,
        unauthorized_message=UNAUTHORIZED_DEVICE_TOKEN_MESSAGE,
    )
    settings = get_settings()

    try:
        payload = decode_device_access_token(
            token=token,
            secret_key=get_device_token_secret_key(),
            algorithm=settings.device_token_algorithm,
        )
        device_id = int(payload.get("sub", "0"))
    except (InvalidTokenError, TypeError, ValueError):
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_TOKEN_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    device = db.scalar(
        select(Device).where(
            Device.id == device_id,
            Device.status == DeviceStatus.ACTIVE,
        )
    )
    if device is None:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_TOKEN_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _touch_device_authentication(device, db)


def authenticate_user_bearer_token(db: Session, authorization: str | None) -> User:
    token = _extract_bearer_token(
        authorization,
        unauthorized_message=UNAUTHORIZED_USER_MESSAGE,
    )
    settings = get_settings()

    try:
        payload = decode_access_token(
            token=token,
            secret_key=get_jwt_secret_key(),
            algorithm=settings.jwt_algorithm,
        )
        user_id = int(payload.get("sub", "0"))
    except (InvalidTokenError, TypeError, ValueError):
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_USER_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_USER_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise AuthenticationError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


def _raise_http_exception(error: AuthenticationError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
        headers=error.headers,
    )


def get_current_device(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Device:
    cached_device = getattr(request.state, "current_device", None)
    if cached_device is not None:
        return cached_device

    try:
        device = authenticate_device_bearer_token(db, authorization)
    except AuthenticationError as error:
        _raise_http_exception(error)

    request.state.current_device = device
    return device


def get_device_by_api_key(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Device:
    cached_device = getattr(request.state, "current_device", None)
    if cached_device is not None:
        return cached_device

    try:
        device = authenticate_device_api_key(db, x_api_key)
    except AuthenticationError as error:
        log_security_event(
            request=request,
            event_type="device.api_key_rejected",
            category=SecurityEventCategory.AUTHENTICATION,
            severity=SecurityEventSeverity.HIGH,
            outcome=SecurityEventOutcome.FAILURE,
            description=error.detail,
            details={
                "mechanism": "api_key",
                "status_code": error.status_code,
            },
        )
        _raise_http_exception(error)

    request.state.current_device = device
    return device


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return cached_user

    try:
        user = authenticate_user_bearer_token(db, authorization)
    except AuthenticationError as error:
        _raise_http_exception(error)

    request.state.current_user = user
    return user


def require_roles(*allowed_roles: UserRole):
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            log_security_event(
                request=request,
                event_type="authorization.role_denied",
                category=SecurityEventCategory.AUTHORIZATION,
                severity=SecurityEventSeverity.MEDIUM,
                outcome=SecurityEventOutcome.BLOCKED,
                description="User attempted an action without the required role.",
                details={
                    "current_role": current_user.role.value,
                    "allowed_roles": [role.value for role in allowed_roles],
                },
                actor_type=AuditActorType.USER,
                actor_user_id=current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return dependency
