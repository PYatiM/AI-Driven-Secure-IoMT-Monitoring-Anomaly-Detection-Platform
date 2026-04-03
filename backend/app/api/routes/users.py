from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import require_roles
from backend.app.db.models import User, UserRole
from backend.app.db.session import get_db
from backend.app.schemas.users import UserCreateRequest, UserRead
from backend.app.security.auth import hash_password
from backend.app.services.audit import set_audit_context

router = APIRouter(prefix="/users", tags=["users"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.get(
    "",
    response_model=list[UserRead],
    summary="List users",
)
def list_users(
    request: Request,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    users = list(db.scalars(select(User).order_by(User.id.asc())))
    set_audit_context(
        request,
        action="user.list",
        resource_type="user",
        details={"count": len(users)},
    )
    return users


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(
    request: Request,
    payload: UserCreateRequest,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> UserRead:
    email = _normalize_email(payload.email)
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create user because the email already exists.",
        ) from None

    db.refresh(user)
    set_audit_context(
        request,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role.value, "is_active": user.is_active},
    )
    return user
