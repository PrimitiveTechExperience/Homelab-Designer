import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    # Confirm-password is a frontend-only check; the API receives a single password.
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError("Username must be 3-32 characters: letters, digits, _ . -")
        return value


class LoginRequest(BaseModel):
    identifier: str = Field(description="Username or email")
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr
    is_verified: bool
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
