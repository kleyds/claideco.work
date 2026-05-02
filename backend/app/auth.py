import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def require_api_key(x_api_key: str = Header(..., description="Your API key")) -> str:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(500, "Server misconfigured: API_KEY env var not set")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid API key")
    return x_api_key


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _secret_key() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        if os.getenv("APP_ENV", "development") != "production":
            return "dev-only-change-me"
        raise HTTPException(500, "Server misconfigured: SECRET_KEY env var not set")
    return secret


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user.id), "email": user.email, "exp": expires_at}
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def user_from_token(token: str, db: Session) -> User:
    credentials_error = HTTPException(401, "Could not validate credentials")
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise credentials_error from exc

    if not user_id:
        raise credentials_error

    user = db.get(User, int(user_id))
    if not user:
        raise credentials_error

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return user_from_token(token, db)
