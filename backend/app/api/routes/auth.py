from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User, utcnow
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    ResendVerificationRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]

# Verified against when the account doesn't exist, so login timing doesn't reveal that.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, background: BackgroundTasks, db: DbSession) -> User:
    taken = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == body.username.lower(),
                func.lower(User.email) == body.email.lower(),
            )
        )
    )
    if taken is not None:
        field = "Username" if taken.username.lower() == body.username.lower() else "Email"
        raise HTTPException(status.HTTP_409_CONFLICT, f"{field} is already registered")

    user = User(
        username=body.username, email=body.email, password_hash=hash_password(body.password)
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # lost a race with a concurrent signup
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username or email is already registered"
        ) from None
    background.add_task(
        send_verification_email, user.email, user.username, create_token(user.id, "verify")
    )
    return user


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: VerifyEmailRequest, db: DbSession) -> MessageResponse:
    user_id = decode_token(body.token, "verify")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link")
    if not user.is_verified:
        user.email_verified_at = utcnow()
        db.commit()
    return MessageResponse(message="Email verified")


@router.post(
    "/resend-verification", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def resend_verification(
    body: ResendVerificationRequest, background: BackgroundTasks, db: DbSession
) -> MessageResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user is not None and not user.is_verified:
        background.add_task(
            send_verification_email, user.email, user.username, create_token(user.id, "verify")
        )
    # Same response either way so this can't be used to probe which emails are registered.
    return MessageResponse(message="If that account needs verification, an email has been sent")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    ident = body.identifier.lower()
    user = db.scalar(
        select(User).where(or_(func.lower(User.username) == ident, func.lower(User.email) == ident))
    )
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not verified")
    return TokenResponse(access_token=create_token(user.id, "access"))


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
