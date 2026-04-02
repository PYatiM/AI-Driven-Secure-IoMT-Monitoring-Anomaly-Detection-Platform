from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import UserRole


class UserCreateRequest(BaseModel):
    full_name: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.ANALYST
    is_active: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
