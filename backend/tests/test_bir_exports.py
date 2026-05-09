from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BankTransaction, Client, Receipt, ReceiptDataRecord, Reconciliation, User


def _csv_rows(response) -> list[dict[str, str]]:
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.text)))


def _approved_receipt(
    db: Session,
    client: Client,
    user: User,
    *,
    vendor: str,
    vendor_tin: str,
    reference: str,
    date: str,
    total: float,
    vatable_amount: float = 0.0,
    vat_amount: float = 0.0,
    vat_type: str = "vatable",
    doc_type: str = "official_receipt",
) -> Receipt:
    receipt = Receipt(
        client_id=client.id,
        user_id=user.id,
        file_path="/tmp/bir-receipt.pdf",
        original_name="bir-receipt.pdf",
        mime_type="application/pdf",
        file_size_kb=1,
        status="approved",
    )
    db.add(receipt)
    db.flush()
    db.add(
        ReceiptDataRecord(
            receipt_id=receipt.id,
            vendor=vendor,
            vendor_tin=vendor_tin,
            or_number=reference,
            date=date,
            currency="PHP",
            vatable_amount=vatable_amount,
            vat_amount=vat_amount,
            total=total,
            vat_type=vat_type,
            doc_type=doc_type,
            confidence=0.95,
        )
    )
    db.commit()
    db.refresh(receipt)
    return receipt


def test_slsp_export_groups_approved_purchases_by_supplier(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
):
    _approved_receipt(
        db_session,
        client_record,
        current_user,
        vendor="Acme Supplies",
        vendor_tin="111-222-333-000",
        reference="OR-1",
        date="2026-04-05",
        total=1120.0,
        vatable_amount=1000.0,
        vat_amount=120.0,
    )
    _approved_receipt(
        db_session,
        client_record,
        current_user,
        vendor="Acme Supplies",
        vendor_tin="111-222-333-000",
        reference="OR-2",
        date="2026-05-05",
        total=500.0,
        vat_type="zero_rated",
        doc_type="sales_invoice",
    )
    _approved_receipt(
        db_session,
        client_record,
        current_user,
        vendor="Outside Quarter",
        vendor_tin="999-999-999-000",
        reference="OR-3",
        date="2026-08-01",
        total=999.0,
    )

    response = api_client.get(f"/v1/clients/{client_record.id}/exports/slsp", params={"quarter": "2026-Q2"})

    assert response.status_code == 200
    assert 'filename="slsp-client-' in response.headers["content-disposition"]
    rows = _csv_rows(response)
    assert rows == [
        {
            "Quarter": "2026-Q2",
            "Supplier TIN": "111-222-333-000",
            "Supplier Name": "Acme Supplies",
            "Receipt Count": "2",
            "Exempt Purchases": "0.0",
            "Zero-Rated Purchases": "500.0",
            "Taxable Net (VATable)": "1000.0",
            "Input VAT": "120.0",
            "Services Subtotal": "1120.0",
            "Gross Total": "1620.0",
        }
    ]


def test_sawt_export_lists_2307_reconciliations_and_withheld_tax(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
):
    receipt = _approved_receipt(
        db_session,
        client_record,
        current_user,
        vendor="Acme Services",
        vendor_tin="111-222-333-000",
        reference="OR-2307",
        date="2026-04-10",
        total=1000.0,
        vatable_amount=892.86,
        vat_amount=107.14,
    )
    transaction = BankTransaction(
        client_id=client_record.id,
        user_id=current_user.id,
        bank_name="BDO",
        transaction_date="2026-04-12",
        description="Acme Services payment",
        amount=980.0,
        direction="outflow",
        status="reconciled",
    )
    db_session.add(transaction)
    db_session.flush()
    db_session.add(
        Reconciliation(
            client_id=client_record.id,
            user_id=current_user.id,
            receipt_id=receipt.id,
            bank_transaction_id=transaction.id,
            requires_2307="true",
            form_2307_status="attached",
            form_2307_original_name="form-2307.pdf",
        )
    )
    db_session.commit()

    response = api_client.get(f"/v1/clients/{client_record.id}/exports/sawt", params={"quarter": "2026-Q2"})

    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows == [
        {
            "Quarter": "2026-Q2",
            "Date Paid": "2026-04-12",
            "Payee TIN": "111-222-333-000",
            "Payee Name": "Acme Services",
            "Reference (OR/SI)": "OR-2307",
            "Gross Income": "1000.0",
            "Tax Withheld": "20.0",
            "ATC (estimated)": "WC160 (2%)",
            "Form 2307 Status": "attached",
            "Form 2307 Filename": "form-2307.pdf",
        }
    ]


def test_journal_export_splits_input_vat_and_uses_matched_bank_account(
    api_client: TestClient,
    db_session: Session,
    client_record: Client,
    current_user: User,
):
    receipt = _approved_receipt(
        db_session,
        client_record,
        current_user,
        vendor="Acme Services",
        vendor_tin="111-222-333-000",
        reference="OR-JOURNAL",
        date="2026-05-10",
        total=1120.0,
        vatable_amount=1000.0,
        vat_amount=120.0,
    )
    transaction = BankTransaction(
        client_id=client_record.id,
        user_id=current_user.id,
        bank_name="BDO",
        transaction_date="2026-05-11",
        description="Payment",
        amount=1120.0,
        direction="outflow",
        status="reconciled",
    )
    db_session.add(transaction)
    db_session.flush()
    db_session.add(
        Reconciliation(
            client_id=client_record.id,
            user_id=current_user.id,
            receipt_id=receipt.id,
            bank_transaction_id=transaction.id,
            requires_2307="false",
        )
    )
    db_session.commit()

    response = api_client.get(f"/v1/clients/{client_record.id}/exports/journal", params={"month": "2026-05"})

    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows[0] == {
        "Date": "2026-05-10",
        "Particulars": "Acme Services (OR-JOURNAL)",
        "PR": "",
        "Debit": "1000.0",
        "Credit": "",
    }
    assert rows[1]["Particulars"] == "Input VAT"
    assert rows[1]["Debit"] == "120.0"
    assert rows[2]["Particulars"].strip().startswith("Cash in Bank")
    assert rows[2]["Particulars"].strip().endswith("BDO")
    assert rows[2]["Credit"] == "1120.0"


def test_compliance_deadlines_returns_upcoming_static_schedule(
    api_client: TestClient,
    client_record: Client,
):
    response = api_client.get(
        f"/v1/clients/{client_record.id}/compliance/deadlines",
        params={"as_of": "2026-02-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["as_of"] == "2026-02-01"
    forms = {deadline["form"] for deadline in payload["deadlines"]}
    assert {"1601-C", "2550M", "2550Q + SLSP", "1601-EQ + QAP", "1701Q / 1702Q + SAWT"}.issubset(forms)
    assert payload["deadlines"] == sorted(payload["deadlines"], key=lambda item: item["due"])
