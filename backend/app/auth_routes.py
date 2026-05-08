import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.email_service import send_verification_email
from app.models import User
from app.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthResponse,
    MeResponse,
    RegisterResponse,
    ResendVerificationRequest,
    SimpleMessageResponse,
    VerifyEmailRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

VERIFICATION_TOKEN_TTL_HOURS = 24
VERIFICATION_RESEND_COOLDOWN_SECONDS = 60


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_verification_token(user: User) -> str:
    token = secrets.token_urlsafe(48)
    user.verification_token = token
    user.verification_token_expires_at = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_TTL_HOURS)
    user.verification_sent_at = datetime.utcnow()
    return token


def _send_verification_or_log(user: User, token: str) -> None:
    try:
        send_verification_email(to_email=user.email, name=user.name, token=token)
    except Exception:
        # Logged inside send_verification_email; we don't want to fail registration if SMTP is down.
        # The user can request a fresh link via /auth/resend-verification.
        pass


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(422, "Enter a valid email address")

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise HTTPException(409, "Email is already registered")

    user = User(
        name=payload.name.strip(),
        email=email,
        password=hash_password(payload.password),
        is_verified=False,
    )
    token = _issue_verification_token(user)
    db.add(user)
    db.commit()
    db.refresh(user)

    _send_verification_or_log(user, token)

    return RegisterResponse(
        message="Account created. Check your email for a verification link.",
        email=user.email,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_verified:
        raise HTTPException(403, "Please verify your email before logging in.")

    return AuthResponse(access_token=create_access_token(user), user=user)


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(422, "Verification token is required")

    user = db.scalar(select(User).where(User.verification_token == token))
    if not user:
        raise HTTPException(400, "Invalid or expired verification link")

    expires_at = user.verification_token_expires_at
    if expires_at and expires_at < datetime.utcnow():
        raise HTTPException(400, "Verification link has expired. Request a new one.")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    db.commit()
    db.refresh(user)

    return AuthResponse(access_token=create_access_token(user), user=user)


@router.post("/resend-verification", response_model=SimpleMessageResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    # Always return the same message to avoid leaking which emails exist.
    generic_response = SimpleMessageResponse(
        message="If that email is registered and unverified, a fresh verification link is on its way."
    )
    if not user or user.is_verified:
        return generic_response

    if user.verification_sent_at:
        elapsed = (datetime.utcnow() - user.verification_sent_at).total_seconds()
        if elapsed < VERIFICATION_RESEND_COOLDOWN_SECONDS:
            return generic_response

    token = _issue_verification_token(user)
    db.commit()
    _send_verification_or_log(user, token)
    return generic_response


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(user=current_user)
