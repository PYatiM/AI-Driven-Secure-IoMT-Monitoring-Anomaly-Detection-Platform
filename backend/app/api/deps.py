from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Device, DeviceStatus
from backend.app.db.session import get_db
from backend.app.security.api_keys import build_api_key_lookup


UNAUTHORIZED_DEVICE_MESSAGE = "Invalid or missing device API key."


def get_current_device(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Device:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_MESSAGE,
        )

    api_key_prefix, api_key_hash = build_api_key_lookup(x_api_key)
    device = db.scalar(
        select(Device).where(
            Device.api_key_prefix == api_key_prefix,
            Device.api_key_hash == api_key_hash,
            Device.status == DeviceStatus.ACTIVE,
        )
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_DEVICE_MESSAGE,
        )

    device.last_authenticated_at = datetime.now(timezone.utc)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device
