from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_device
from backend.app.db.models import Device, DeviceStatus
from backend.app.db.session import get_db
from backend.app.schemas.devices import (
    DeviceRead,
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
)
from backend.app.security.api_keys import generate_device_api_key

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "/register",
    response_model=DeviceRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new device",
)
def register_device(
    payload: DeviceRegistrationRequest,
    db: Session = Depends(get_db),
) -> DeviceRegistrationResponse:
    existing_device = db.scalar(
        select(Device).where(Device.device_identifier == payload.device_identifier)
    )
    if existing_device is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A device with this identifier already exists.",
        )

    api_key, api_key_prefix, api_key_hash = generate_device_api_key()
    now = datetime.now(timezone.utc)

    device = Device(
        device_identifier=payload.device_identifier,
        name=payload.name,
        device_type=payload.device_type,
        manufacturer=payload.manufacturer,
        model=payload.model,
        firmware_version=payload.firmware_version,
        location=payload.location,
        ip_address=payload.ip_address,
        owner_user_id=payload.owner_user_id,
        status=DeviceStatus.ACTIVE,
        api_key_prefix=api_key_prefix,
        api_key_hash=api_key_hash,
        api_key_created_at=now,
    )

    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to register device because the identifier already exists.",
        ) from None

    db.refresh(device)
    return DeviceRegistrationResponse(
        id=device.id,
        device_identifier=device.device_identifier,
        name=device.name,
        device_type=device.device_type,
        manufacturer=device.manufacturer,
        model=device.model,
        firmware_version=device.firmware_version,
        location=device.location,
        ip_address=device.ip_address,
        status=device.status,
        owner_user_id=device.owner_user_id,
        created_at=device.created_at,
        updated_at=device.updated_at,
        api_key_prefix=device.api_key_prefix,
        api_key_created_at=device.api_key_created_at,
        last_authenticated_at=device.last_authenticated_at,
        api_key=api_key,
        message="Store this API key securely. It is only returned once.",
    )


@router.get(
    "/me",
    response_model=DeviceRead,
    summary="Get the currently authenticated device",
)
def get_authenticated_device(
    current_device: Device = Depends(get_current_device),
) -> DeviceRead:
    return current_device
