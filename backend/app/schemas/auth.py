from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UserRole


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    branch_id: int | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class MessageResponse(BaseModel):
    message: str


class BranchScopeResponse(BaseModel):
    all_branches: bool
    branch_ids: list[int]
