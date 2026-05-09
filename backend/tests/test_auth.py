from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User


def test_register_creates_unverified_user_and_blocks_login_until_verified(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    sent_emails = []
    monkeypatch.setattr("app.auth_routes.send_verification_email", lambda **kwargs: sent_emails.append(kwargs))

    register = api_client.post(
        "/v1/auth/register",
        json={"name": "New User", "email": "New@Example.com", "password": "password123"},
    )

    assert register.status_code == 201
    assert register.json()["email"] == "new@example.com"
    user = db_session.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert user.is_verified is False
    assert user.verification_token
    assert sent_emails[0]["to_email"] == "new@example.com"

    blocked_login = api_client.post(
        "/v1/auth/login",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert blocked_login.status_code == 403
    assert blocked_login.json()["detail"] == "Please verify your email before logging in."


def test_verify_email_marks_user_verified_and_returns_access_token(
    api_client: TestClient,
    db_session: Session,
):
    user = User(
        name="Verify Me",
        email="verify@example.com",
        password=hash_password("password123"),
        is_verified=False,
        verification_token="valid-token",
        verification_token_expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db_session.add(user)
    db_session.commit()

    response = api_client.post("/v1/auth/verify-email", json={"token": "valid-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "verify@example.com"
    db_session.refresh(user)
    assert user.is_verified is True
    assert user.verification_token is None
    assert user.verification_token_expires_at is None


def test_duplicate_registration_is_rejected(
    api_client: TestClient,
    db_session: Session,
):
    db_session.add(
        User(
            name="Existing User",
            email="taken@example.com",
            password=hash_password("password123"),
            is_verified=True,
        )
    )
    db_session.commit()

    response = api_client.post(
        "/v1/auth/register",
        json={"name": "Other User", "email": "taken@example.com", "password": "password123"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already registered"


def test_resend_verification_obeys_cooldown_and_avoids_account_leaks(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    sent_emails = []
    monkeypatch.setattr("app.auth_routes.send_verification_email", lambda **kwargs: sent_emails.append(kwargs))
    user = User(
        name="Cooldown User",
        email="cooldown@example.com",
        password=hash_password("password123"),
        is_verified=False,
        verification_token="existing-token",
        verification_token_expires_at=datetime.utcnow() + timedelta(hours=1),
        verification_sent_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()

    cooling_down = api_client.post("/v1/auth/resend-verification", json={"email": "cooldown@example.com"})
    assert cooling_down.status_code == 200
    assert sent_emails == []
    db_session.refresh(user)
    assert user.verification_token == "existing-token"

    missing_user = api_client.post("/v1/auth/resend-verification", json={"email": "missing@example.com"})
    assert missing_user.status_code == 200
    assert missing_user.json() == cooling_down.json()
