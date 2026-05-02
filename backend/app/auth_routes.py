from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import AuthLoginRequest, AuthRegisterRequest, AuthResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=AuthResponse, status_code=201)
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(access_token=create_access_token(user), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, "Invalid email or password")

    return AuthResponse(access_token=create_access_token(user), user=user)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(user=current_user)
