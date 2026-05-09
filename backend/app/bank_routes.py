from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.client_routes import _client_or_404
from app.database import get_db
from app.models import BankTransaction, Receipt, ReceiptDataRecord, Reconciliation, User
from app.schemas import (
    BankImportResponse,
    BankTransactionsResponse,
    BulkCategorizeRequest,
    BulkCategorizeResponse,
    Form2307UpdateRequest,
    MatchSuggestion,
    MatchSuggestionsResponse,
    ReconcileRequest,
    ReconciliationPublic,
    ReconciliationsResponse,
)

router = APIRouter(prefix="/clients/{client_id}/bank", tags=["bank"])

FORM_2307_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
BANK_TEMPLATES = {
    "generic": {
        "label": "Generic",
        "date": ["date", "transaction date", "posting date", "post date"],
        "description": ["description", "details", "particulars", "merchant", "remarks"],
        "reference": ["reference", "ref", "transaction id", "check no", "cheque no"],
        "amount": ["amount", "transaction amount", "amt"],
        "debit": ["debit", "withdrawal", "withdrawals", "debit amount"],
        "credit": ["credit", "deposit", "deposits", "credit amount"],
    },
    "bdo": {
        "label": "BDO",
        "date": ["posting date", "transaction date", "date"],
        "description": ["description", "transaction description", "details"],
        "reference": ["reference no.", "reference number", "ref no", "ref"],
        "amount": ["amount"],
        "debit": ["debit", "withdrawal"],
        "credit": ["credit", "deposit"],
    },
    "bpi": {
        "label": "BPI",
        "date": ["transaction date", "posted date", "date"],
        "description": ["description", "transaction details", "remarks"],
        "reference": ["branch", "reference", "confirmation no.", "trace no."],
        "amount": ["amount"],
        "debit": ["withdrawal", "debit"],
        "credit": ["deposit", "credit"],
    },
    "metrobank": {
        "label": "Metrobank",
        "date": ["transaction date", "posting date", "date"],
        "description": ["particulars", "description", "transaction particulars"],
        "reference": ["reference no", "reference", "check no"],
        "amount": ["amount"],
        "debit": ["debit", "withdrawal"],
        "credit": ["credit", "deposit"],
    },
    "unionbank": {
        "label": "UnionBank",
        "date": ["date", "transaction date", "posted date"],
        "description": ["description", "transaction details", "merchant name"],
        "reference": ["reference number", "reference no.", "ref no.", "trace number"],
        "amount": ["amount", "transaction amount"],
        "debit": ["debit amount", "debit", "withdrawal"],
        "credit": ["credit amount", "credit", "deposit"],
    },
}


def _first(row: dict[str, str], keys: list[str]) -> str:
    normalized = {key.strip().lower(): (value or "") for key, value in row.items() if key}
    for key in keys:
        value = normalized.get(key)
        if value:
            return value.strip()
    return ""


def _parse_amount(value: str) -> float:
    cleaned = value.replace(",", "").replace("PHP", "").replace("₱", "").strip()
    if not cleaned:
        return 0.0
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    return float(cleaned)


def _parse_date(value: str) -> Optional[str]:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def _template_or_422(template: str) -> dict[str, list[str] | str]:
    key = template.strip().lower()
    if key not in BANK_TEMPLATES:
        raise HTTPException(422, f"bank_template must be one of: {sorted(BANK_TEMPLATES)}")
    return BANK_TEMPLATES[key]


def _upload_root() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()


def _extension(filename: Optional[str], content_type: Optional[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        return suffix
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(content_type or "", "")


def _reconciliation_statement(client_id: int, user_id: int):
    return (
        select(Reconciliation)
        .options(
            selectinload(Reconciliation.receipt).selectinload(Receipt.data),
            selectinload(Reconciliation.receipt).selectinload(Receipt.line_items),
            selectinload(Reconciliation.bank_transaction),
        )
        .where(
            Reconciliation.client_id == client_id,
            Reconciliation.user_id == user_id,
        )
    )


def _reconciliation_or_404(reconciliation_id: int, client_id: int, user_id: int, db: Session) -> Reconciliation:
    reconciliation = db.scalar(
        _reconciliation_statement(client_id, user_id).where(Reconciliation.id == reconciliation_id)
    )
    if not reconciliation:
        raise HTTPException(404, "Reconciliation not found")
    return reconciliation


def _clean_notes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _apply_form_2307_status(reconciliation: Reconciliation, status: str) -> None:
    now = datetime.utcnow()
    if status == "attached" and not reconciliation.form_2307_file_path:
        raise HTTPException(422, "Upload a Form 2307 file before marking it attached")

    reconciliation.form_2307_status = status
    if status in {"requested", "received", "attached"} and not reconciliation.form_2307_requested_at:
        reconciliation.form_2307_requested_at = now
    if status in {"received", "attached"} and not reconciliation.form_2307_received_at:
        reconciliation.form_2307_received_at = now


def _transaction_fingerprint(transaction: BankTransaction) -> tuple[Optional[str], float, str, str, str]:
    return (
        transaction.transaction_date,
        round(transaction.amount, 2),
        transaction.direction,
        (transaction.reference or "").strip().lower(),
        transaction.description.strip().lower(),
    )


def _transaction_from_row(
    client_id: int,
    user_id: int,
    row: dict[str, str],
    bank_name: Optional[str],
    template: dict[str, list[str] | str],
) -> BankTransaction:
    debit = _parse_amount(_first(row, template["debit"]))
    credit = _parse_amount(_first(row, template["credit"]))
    raw_amount = _first(row, template["amount"])
    if not raw_amount and debit == 0 and credit == 0:
        raise ValueError("missing amount/debit/credit value")
    amount = _parse_amount(raw_amount) if raw_amount else credit - debit
    direction = "inflow" if amount >= 0 else "outflow"
    transaction_date = _parse_date(_first(row, template["date"]))
    description = _first(row, template["description"]) or "Bank transaction"

    return BankTransaction(
        client_id=client_id,
        user_id=user_id,
        bank_name=bank_name,
        transaction_date=transaction_date,
        description=description,
        reference=_first(row, template["reference"]),
        amount=abs(amount),
        direction=direction,
        raw_json={**row, "_bank_template": template["label"]},
    )


@router.post("/import", response_model=BankImportResponse, status_code=201)
async def import_bank_csv(
    client_id: int,
    file: UploadFile = File(...),
    bank_name: Optional[str] = None,
    bank_template: str = "generic",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(400, "Upload a CSV bank export")

    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV must include a header row")
    template = _template_or_422(bank_template)

    existing_transactions = db.scalars(
        select(BankTransaction).where(
            BankTransaction.client_id == client_id,
            BankTransaction.user_id == current_user.id,
        )
    ).all()
    fingerprints = {_transaction_fingerprint(transaction) for transaction in existing_transactions}

    transactions = []
    errors = []
    skipped_duplicates = 0
    for index, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            transaction = _transaction_from_row(client_id, current_user.id, row, bank_name, template)
        except ValueError as exc:
            errors.append(f"Row {index}: {exc}")
            continue

        fingerprint = _transaction_fingerprint(transaction)
        if fingerprint in fingerprints:
            skipped_duplicates += 1
            continue
        fingerprints.add(fingerprint)
        transactions.append(transaction)

    db.add_all(transactions)
    db.commit()
    for transaction in transactions:
        db.refresh(transaction)

    return BankImportResponse(
        imported=len(transactions),
        skipped_duplicates=skipped_duplicates,
        skipped_errors=len(errors),
        errors=errors[:10],
        transactions=transactions,
    )


@router.get("/transactions", response_model=BankTransactionsResponse)
def list_bank_transactions(
    client_id: int,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    statement = select(BankTransaction).where(
        BankTransaction.client_id == client_id,
        BankTransaction.user_id == current_user.id,
    )
    if status:
        statement = statement.where(BankTransaction.status == status)
    transactions = db.scalars(statement.order_by(BankTransaction.transaction_date.desc())).all()
    return BankTransactionsResponse(transactions=transactions)


@router.get("/reconciliations", response_model=ReconciliationsResponse)
def list_reconciliations(
    client_id: int,
    requires_2307: Optional[bool] = None,
    form_2307_status: Optional[str] = Query(None, pattern=r"^(missing|requested|received|attached)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    statement = _reconciliation_statement(client_id, current_user.id)
    if requires_2307 is not None:
        statement = statement.where(Reconciliation.requires_2307 == ("true" if requires_2307 else "false"))
    if form_2307_status:
        statement = statement.where(Reconciliation.form_2307_status == form_2307_status)
    reconciliations = db.scalars(statement.order_by(Reconciliation.created_at.desc())).all()
    return ReconciliationsResponse(reconciliations=reconciliations)


@router.patch("/reconciliations/{reconciliation_id}/2307", response_model=ReconciliationPublic)
def update_form_2307_status(
    client_id: int,
    reconciliation_id: int,
    payload: Form2307UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    reconciliation = _reconciliation_or_404(reconciliation_id, client_id, current_user.id, db)
    if reconciliation.requires_2307 != "true":
        raise HTTPException(422, "This reconciliation does not require Form 2307")

    if payload.status:
        _apply_form_2307_status(reconciliation, payload.status)
    if payload.notes is not None:
        reconciliation.form_2307_notes = _clean_notes(payload.notes)
    db.commit()
    db.refresh(reconciliation)
    return reconciliation


@router.post("/reconciliations/{reconciliation_id}/2307/file", response_model=ReconciliationPublic)
async def upload_form_2307_file(
    client_id: int,
    reconciliation_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    reconciliation = _reconciliation_or_404(reconciliation_id, client_id, current_user.id, db)
    if reconciliation.requires_2307 != "true":
        raise HTTPException(422, "This reconciliation does not require Form 2307")
    if file.content_type not in FORM_2307_TYPES:
        raise HTTPException(400, "Upload a PDF, JPEG, PNG, or WebP Form 2307 file")

    content = await file.read()
    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"{file.filename or 'File'} is too large (max {max_mb} MB)")

    target_dir = _upload_root() / str(current_user.id) / str(client_id) / "form_2307"
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{reconciliation.id}-{uuid.uuid4().hex}{_extension(file.filename, file.content_type)}"
    file_path = target_dir / stored_name
    file_path.write_bytes(content)

    reconciliation.form_2307_file_path = str(file_path)
    reconciliation.form_2307_original_name = file.filename
    reconciliation.form_2307_mime_type = file.content_type
    reconciliation.form_2307_uploaded_at = datetime.utcnow()
    _apply_form_2307_status(reconciliation, "attached")
    db.commit()
    db.refresh(reconciliation)
    return reconciliation


@router.get("/reconciliations/{reconciliation_id}/2307/file")
def get_form_2307_file(
    client_id: int,
    reconciliation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    reconciliation = _reconciliation_or_404(reconciliation_id, client_id, current_user.id, db)
    if not reconciliation.form_2307_file_path:
        raise HTTPException(404, "Form 2307 file not found")

    path = Path(reconciliation.form_2307_file_path)
    if not path.exists():
        raise HTTPException(404, "Form 2307 file not found")
    return FileResponse(
        path,
        media_type=reconciliation.form_2307_mime_type,
        filename=reconciliation.form_2307_original_name,
        content_disposition_type="inline",
    )


def _date_distance_days(left: Optional[str], right: Optional[str]) -> Optional[int]:
    if not left or not right:
        return None
    try:
        return abs((date.fromisoformat(left) - date.fromisoformat(right)).days)
    except ValueError:
        return None


def _name_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def _score_match(transaction: BankTransaction, receipt: Receipt) -> Tuple[float, list[str], Optional[float], bool]:
    if not receipt.data:
        return 0.0, [], None, False

    score = 0.0
    reasons: list[str] = []
    invoice_total = receipt.data.total or 0.0
    amount_diff = abs(transaction.amount - invoice_total)
    withholding_1 = abs(transaction.amount - invoice_total * 0.99)
    withholding_2 = abs(transaction.amount - invoice_total * 0.98)
    withholding_variance = None
    requires_2307 = False

    if amount_diff <= 1:
        score += 0.45
        reasons.append("exact amount")
    elif withholding_1 <= 1 or withholding_2 <= 1:
        score += 0.38
        withholding_variance = 0.01 if withholding_1 <= withholding_2 else 0.02
        requires_2307 = True
        reasons.append(f"{int(withholding_variance * 100)}% withholding variance")

    days = _date_distance_days(transaction.transaction_date, receipt.data.date)
    if days is not None and days <= 7:
        score += 0.25
        reasons.append(f"date within {days} day{'s' if days != 1 else ''}")

    name_similarity = _name_score(transaction.description, receipt.data.vendor or "")
    if name_similarity >= 0.45:
        score += min(0.3, name_similarity * 0.3)
        reasons.append("vendor name similarity")

    return round(score, 3), reasons, withholding_variance, requires_2307


def _approved_receipts_statement(client_id: int, user_id: int):
    return (
        select(Receipt)
        .options(selectinload(Receipt.data), selectinload(Receipt.line_items))
        .join(ReceiptDataRecord, ReceiptDataRecord.receipt_id == Receipt.id)
        .where(
            Receipt.client_id == client_id,
            Receipt.user_id == user_id,
            Receipt.status == "approved",
        )
    )


@router.get("/transactions/{transaction_id}/matches", response_model=MatchSuggestionsResponse)
def match_suggestions(
    client_id: int,
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    transaction = db.scalar(
        select(BankTransaction).where(
            BankTransaction.id == transaction_id,
            BankTransaction.client_id == client_id,
            BankTransaction.user_id == current_user.id,
        )
    )
    if not transaction:
        raise HTTPException(404, "Bank transaction not found")

    receipts = db.scalars(_approved_receipts_statement(client_id, current_user.id)).all()

    suggestions = []
    for receipt in receipts:
        score, reasons, withholding_variance, requires_2307 = _score_match(transaction, receipt)
        if score >= 0.35:
            suggestions.append(
                MatchSuggestion(
                    receipt=receipt,
                    score=score,
                    reasons=reasons,
                    withholding_variance=withholding_variance,
                    requires_2307=requires_2307,
                )
            )

    suggestions.sort(key=lambda item: item.score, reverse=True)
    return MatchSuggestionsResponse(transaction=transaction, suggestions=suggestions[:5])


@router.get("/transactions/{transaction_id}/manual-matches", response_model=MatchSuggestionsResponse)
def manual_match_search(
    client_id: int,
    transaction_id: int,
    q: str = Query("", max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    transaction = db.scalar(
        select(BankTransaction).where(
            BankTransaction.id == transaction_id,
            BankTransaction.client_id == client_id,
            BankTransaction.user_id == current_user.id,
        )
    )
    if not transaction:
        raise HTTPException(404, "Bank transaction not found")

    statement = _approved_receipts_statement(client_id, current_user.id)
    query = q.strip()
    if query:
        like_query = f"%{query}%"
        statement = statement.where(
            ReceiptDataRecord.vendor.ilike(like_query)
            | ReceiptDataRecord.or_number.ilike(like_query)
            | ReceiptDataRecord.si_number.ilike(like_query)
            | Receipt.original_name.ilike(like_query)
        )

    matched_receipt_ids = select(Reconciliation.receipt_id).where(
        Reconciliation.client_id == client_id,
        Reconciliation.user_id == current_user.id,
    )
    receipts = db.scalars(statement.where(Receipt.id.not_in(matched_receipt_ids)).limit(20)).all()

    suggestions = []
    for receipt in receipts:
        score, reasons, withholding_variance, requires_2307 = _score_match(transaction, receipt)
        if not reasons:
            reasons = ["manual search"]
        suggestions.append(
            MatchSuggestion(
                receipt=receipt,
                score=score,
                reasons=reasons,
                withholding_variance=withholding_variance,
                requires_2307=requires_2307,
            )
        )

    suggestions.sort(key=lambda item: item.score, reverse=True)
    return MatchSuggestionsResponse(transaction=transaction, suggestions=suggestions)


@router.post("/transactions/{transaction_id}/reconcile", response_model=ReconciliationPublic, status_code=201)
def reconcile_transaction(
    client_id: int,
    transaction_id: int,
    payload: ReconcileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    transaction = db.scalar(
        select(BankTransaction).where(
            BankTransaction.id == transaction_id,
            BankTransaction.client_id == client_id,
            BankTransaction.user_id == current_user.id,
        )
    )
    if not transaction:
        raise HTTPException(404, "Bank transaction not found")
    if transaction.status == "reconciled":
        raise HTTPException(409, "Bank transaction is already reconciled")

    receipt = db.scalar(
        select(Receipt).where(
            Receipt.id == payload.receipt_id,
            Receipt.client_id == client_id,
            Receipt.user_id == current_user.id,
            Receipt.status == "approved",
        )
    )
    if not receipt:
        raise HTTPException(404, "Approved receipt not found")

    existing = db.scalar(
        select(Reconciliation).where(
            Reconciliation.bank_transaction_id == transaction.id,
        )
    )
    if existing:
        return existing

    reconciliation = Reconciliation(
        client_id=client_id,
        user_id=current_user.id,
        receipt_id=receipt.id,
        bank_transaction_id=transaction.id,
        status="matched",
        match_score=payload.match_score,
        requires_2307="true" if payload.requires_2307 else "false",
        form_2307_status="missing",
    )
    transaction.status = "reconciled"
    db.add(reconciliation)
    db.commit()
    db.refresh(reconciliation)
    return reconciliation


@router.delete("/reconciliations/{reconciliation_id}", status_code=204)
def delete_reconciliation(
    client_id: int,
    reconciliation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    reconciliation = _reconciliation_or_404(reconciliation_id, client_id, current_user.id, db)
    transaction = reconciliation.bank_transaction
    if transaction:
        transaction.status = "unreconciled"
    db.delete(reconciliation)
    db.commit()
    return Response(status_code=204)


@router.patch("/transactions/category", response_model=BulkCategorizeResponse)
def bulk_categorize_transactions(
    client_id: int,
    payload: BulkCategorizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    if not payload.transaction_ids:
        raise HTTPException(422, "Select at least one transaction")

    transactions = db.scalars(
        select(BankTransaction).where(
            BankTransaction.client_id == client_id,
            BankTransaction.user_id == current_user.id,
            BankTransaction.id.in_(payload.transaction_ids),
        )
    ).all()
    if len(transactions) != len(set(payload.transaction_ids)):
        raise HTTPException(404, "One or more bank transactions were not found")

    for transaction in transactions:
        transaction.category = payload.category.strip()

    db.commit()
    for transaction in transactions:
        db.refresh(transaction)

    return BulkCategorizeResponse(updated=len(transactions), transactions=transactions)
