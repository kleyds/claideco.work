from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Client, ClientUploadLink, Receipt, User


def _pdf_file(name: str = "receipt.pdf", content: bytes = b"%PDF-1.4\n%%EOF\n"):
    return ("files", (name, content, "application/pdf"))


def _receipt_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Receipt)) or 0


def test_authenticated_upload_rejects_too_many_files(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    monkeypatch,
):
    monkeypatch.setenv("MAX_FILES_PER_UPLOAD", "1")

    response = api_client.post(
        f"/v1/clients/{client_record.id}/receipts/upload",
        files=[_pdf_file("first.pdf"), _pdf_file("second.pdf")],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Too many files; max is 1"
    assert _receipt_count(db_session) == 0


def test_authenticated_upload_rejects_oversized_file(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    monkeypatch,
):
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
    oversized_pdf = b"%PDF-1.4\n" + (b"x" * (1024 * 1024 + 1))

    response = api_client.post(
        f"/v1/clients/{client_record.id}/receipts/upload",
        files=[_pdf_file("large.pdf", oversized_pdf)],
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "large.pdf is too large (max 1 MB)"
    assert _receipt_count(db_session) == 0


def test_authenticated_upload_rejects_unsupported_file_type(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
):
    response = api_client.post(
        f"/v1/clients/{client_record.id}/receipts/upload",
        files=[("files", ("notes.txt", b"not a receipt", "text/plain"))],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type: text/plain"
    assert _receipt_count(db_session) == 0


def test_portal_upload_rejects_link_upload_count_overflow(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
):
    link = ClientUploadLink(
        client_id=client_record.id,
        user_id=current_user.id,
        token="portal-limit-token",
        max_uploads=1,
    )
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)

    response = api_client.post(
        f"/v1/portal/{link.token}/upload",
        files=[_pdf_file("first.pdf"), _pdf_file("second.pdf")],
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Only 1 upload(s) remain on this link"
    db_session.refresh(link)
    assert link.uploads_count == 0
    assert link.last_used_at is None
    assert _receipt_count(db_session) == 0


def test_portal_upload_increments_usage_on_success(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
    monkeypatch,
):
    monkeypatch.setattr("app.portal_routes.process_receipt", lambda receipt_id: None)
    monkeypatch.setattr("app.portal_routes.send_portal_upload_notification", lambda **kwargs: None)
    link = ClientUploadLink(
        client_id=client_record.id,
        user_id=current_user.id,
        token="portal-success-token",
        max_uploads=2,
    )
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)

    response = api_client.post(
        f"/v1/portal/{link.token}/upload",
        files=[_pdf_file("receipt.pdf")],
    )

    assert response.status_code == 201
    assert response.json()["receipts"][0]["original_name"] == "receipt.pdf"
    receipt = db_session.scalar(select(Receipt).where(Receipt.upload_link_id == link.id))
    assert receipt is not None
    assert receipt.client_id == client_record.id
    assert receipt.user_id == current_user.id
    db_session.refresh(link)
    assert link.uploads_count == 1
    assert link.last_used_at is not None
