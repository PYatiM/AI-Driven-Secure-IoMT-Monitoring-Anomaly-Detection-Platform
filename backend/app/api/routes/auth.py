from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.models import AuditActorType, User, UserRole
from backend.app.db.session import get_db
from backend.app.schemas.auth import TokenResponse, UserLoginRequest, UserRegistrationRequest
from backend.app.schemas.users import UserRead
from backend.app.security.auth import create_access_token, hash_password, verify_password
from backend.app.security.key_storage import get_jwt_secret_key
from backend.app.services.audit import set_audit_context

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_token_response(user: User) -> TokenResponse:
    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        secret_key=get_jwt_secret_key(),
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expires_minutes,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expires_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register_user(
    request: Request,
    payload: UserRegistrationRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    email = _normalize_email(payload.email)
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    role = UserRole.ADMIN if user_count == 0 else UserRole.ANALYST

    user = User(
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to register user because the email already exists.",
        ) from None

    db.refresh(user)
    set_audit_context(
        request,
        action="user.register",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role.value},
        actor_type=AuditActorType.USER,
        actor_user_id=user.id,
    )
    return _issue_token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate a user and return a JWT",
)
def login_user(
    request: Request,
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    set_audit_context(
        request,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role.value},
        actor_type=AuditActorType.USER,
        actor_user_id=user.id,
    )
    return _issue_token_response(user)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the currently authenticated user",
)
def get_authenticated_user(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UserRead:
    set_audit_context(
        request,
        action="user.read_self",
        resource_type="user",
        resource_id=current_user.id,
    )
    return current_user
