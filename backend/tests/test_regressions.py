from __future__ import annotations

import fitz
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    BankTransaction,
    Client,
    ClientUploadLink,
    Receipt,
    ReceiptDataRecord,
    Reconciliation,
    User,
)


def _receipt_with_data(
    db: Session,
    client: Client,
    user: User,
    *,
    status: str = "approved",
    total: float = 1000.0,
    vendor: str = "Acme Services",
    date: str = "2026-05-01",
) -> Receipt:
    receipt = Receipt(
        client_id=client.id,
        user_id=user.id,
        file_path="/tmp/receipt.pdf",
        original_name="receipt.pdf",
        mime_type="application/pdf",
        file_size_kb=1,
        status=status,
    )
    db.add(receipt)
    db.flush()
    db.add(
        ReceiptDataRecord(
            receipt_id=receipt.id,
            vendor=vendor,
            vendor_tin="111-222-333-000",
            or_number="OR-100",
            date=date,
            currency="PHP",
            vatable_amount=892.86,
            vat_amount=107.14,
            total=total,
            vat_type="vatable",
            doc_type="official_receipt",
            confidence=0.94,
        )
    )
    db.commit()
    db.refresh(receipt)
    return receipt


def test_reconciliation_matching_and_2307_tracking(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
    tmp_path,
):
    receipt = _receipt_with_data(db_session, client_record, current_user)
    transaction = BankTransaction(
        client_id=client_record.id,
        user_id=current_user.id,
        bank_name="BDO",
        transaction_date="2026-05-03",
        description="Payment to Acme Services",
        amount=980.0,
        direction="outflow",
        status="unreconciled",
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    matches = api_client.get(f"/v1/clients/{client_record.id}/bank/transactions/{transaction.id}/matches")
    assert matches.status_code == 200
    suggestion = matches.json()["suggestions"][0]
    assert suggestion["receipt"]["id"] == receipt.id
    assert suggestion["requires_2307"] is True
    assert suggestion["withholding_variance"] == 0.02

    reconcile = api_client.post(
        f"/v1/clients/{client_record.id}/bank/transactions/{transaction.id}/reconcile",
        json={"receipt_id": receipt.id, "match_score": suggestion["score"], "requires_2307": True},
    )
    assert reconcile.status_code == 201
    reconciliation_id = reconcile.json()["id"]
    assert reconcile.json()["form_2307_status"] == "missing"

    requested = api_client.patch(
        f"/v1/clients/{client_record.id}/bank/reconciliations/{reconciliation_id}/2307",
        json={"status": "requested", "notes": "Asked client for signed copy."},
    )
    assert requested.status_code == 200
    assert requested.json()["form_2307_status"] == "requested"
    assert requested.json()["form_2307_notes"] == "Asked client for signed copy."
    assert requested.json()["form_2307_requested_at"] is not None

    file_response = api_client.post(
        f"/v1/clients/{client_record.id}/bank/reconciliations/{reconciliation_id}/2307/file",
        files={"file": ("form2307.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    assert file_response.status_code == 200
    assert file_response.json()["form_2307_status"] == "attached"
    assert file_response.json()["form_2307_original_name"] == "form2307.pdf"
    assert file_response.json()["form_2307_received_at"] is not None

    filtered = api_client.get(
        f"/v1/clients/{client_record.id}/bank/reconciliations",
        params={"requires_2307": "true", "form_2307_status": "attached"},
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["reconciliations"]] == [reconciliation_id]


def test_pdf_preview_renders_selected_page_and_bounds(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
    tmp_path,
):
    pdf_path = tmp_path / "two-page.pdf"
    document = fitz.open()
    for label in ("Page one", "Page two"):
        page = document.new_page()
        page.insert_text((72, 72), label)
    document.save(pdf_path)
    document.close()

    receipt = Receipt(
        client_id=client_record.id,
        user_id=current_user.id,
        file_path=str(pdf_path),
        original_name="two-page.pdf",
        mime_type="application/pdf",
        file_size_kb=1,
        status="done",
    )
    db_session.add(receipt)
    db_session.commit()
    db_session.refresh(receipt)

    preview = api_client.get(f"/v1/receipts/{receipt.id}/preview", params={"page": 2})
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["x-pdf-page"] == "2"
    assert preview.headers["x-pdf-page-count"] == "2"
    assert preview.content.startswith(b"\x89PNG")

    missing_page = api_client.get(f"/v1/receipts/{receipt.id}/preview", params={"page": 3})
    assert missing_page.status_code == 404


def test_portal_comments_create_unread_bookkeeper_state_and_notifications(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
    monkeypatch,
):
    notifications = []

    def fake_comment_notification(**kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr("app.portal_routes.send_portal_comment_notification", fake_comment_notification)

    link = ClientUploadLink(
        client_id=client_record.id,
        user_id=current_user.id,
        token="portal-token",
        label="May receipts",
        max_uploads=5,
    )
    db_session.add(link)
    db_session.flush()
    receipt = Receipt(
        client_id=client_record.id,
        user_id=current_user.id,
        upload_link_id=link.id,
        file_path="/tmp/portal.pdf",
        original_name="portal.pdf",
        mime_type="application/pdf",
        file_size_kb=1,
        status="pending",
    )
    db_session.add(receipt)
    db_session.commit()
    db_session.refresh(receipt)

    comment = api_client.post(
        f"/v1/portal/{link.token}/receipts/{receipt.id}/comments",
        json={"author_name": "Client User", "body": "Please use the corrected TIN."},
    )
    assert comment.status_code == 201
    assert comment.json()["author_type"] == "client"
    assert comment.json()["is_read_by_bookkeeper"] is False
    assert notifications[0]["to_email"] == current_user.email
    assert notifications[0]["commenter_name"] == "Client User"

    detail = api_client.get(f"/v1/receipts/{receipt.id}")
    assert detail.status_code == 200
    assert detail.json()["comment_count"] == 1
    assert detail.json()["unread_portal_comment_count"] == 1
    assert detail.json()["latest_comment"]["body"] == "Please use the corrected TIN."

    read = api_client.post(f"/v1/receipts/{receipt.id}/comments/read")
    assert read.status_code == 200
    assert read.json()["comments"][0]["is_read_by_bookkeeper"] is True

    detail_after_read = api_client.get(f"/v1/receipts/{receipt.id}")
    assert detail_after_read.json()["unread_portal_comment_count"] == 0


def test_client_dashboard_metrics_count_open_work_only(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
):
    pending_receipt = _receipt_with_data(db_session, client_record, current_user, status="pending", total=500)
    approved_receipt = _receipt_with_data(db_session, client_record, current_user, status="approved", total=1000)
    unreconciled = BankTransaction(
        client_id=client_record.id,
        user_id=current_user.id,
        transaction_date="2026-05-05",
        description="Open bank item",
        amount=1000,
        direction="outflow",
        status="unreconciled",
    )
    reconciled = BankTransaction(
        client_id=client_record.id,
        user_id=current_user.id,
        transaction_date="2026-05-06",
        description="Matched bank item",
        amount=980,
        direction="outflow",
        status="reconciled",
    )
    db_session.add_all([unreconciled, reconciled])
    db_session.flush()
    db_session.add_all(
        [
            Reconciliation(
                client_id=client_record.id,
                user_id=current_user.id,
                receipt_id=approved_receipt.id,
                bank_transaction_id=reconciled.id,
                requires_2307="true",
                form_2307_status="missing",
            ),
            Reconciliation(
                client_id=client_record.id,
                user_id=current_user.id,
                receipt_id=pending_receipt.id,
                bank_transaction_id=unreconciled.id,
                requires_2307="true",
                form_2307_status="attached",
            ),
        ]
    )
    db_session.commit()

    response = api_client.get("/v1/clients/metrics")
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics == [
        {
            "client_id": client_record.id,
            "unprocessed_invoices": 1,
            "unreconciled_bank_entries": 1,
            "missing_2307s": 1,
        }
    ]
