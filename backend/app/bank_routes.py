import csv
import io
from datetime import date, datetime
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
    MatchSuggestion,
    MatchSuggestionsResponse,
    ReconcileRequest,
    ReconciliationPublic,
)

router = APIRouter(prefix="/clients/{client_id}/bank", tags=["bank"])


def _first(row: dict[str, str], keys: list[str]) -> str:
    normalized = {key.strip().lower(): value for key, value in row.items()}
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


def _parse_date(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def _transaction_from_row(client_id: int, user_id: int, row: dict[str, str], bank_name: str | None) -> BankTransaction:
    debit = _parse_amount(_first(row, ["debit", "withdrawal", "withdrawals", "debit amount"]))
    credit = _parse_amount(_first(row, ["credit", "deposit", "deposits", "credit amount"]))
    raw_amount = _first(row, ["amount", "transaction amount", "amt"])
    amount = _parse_amount(raw_amount) if raw_amount else credit - debit
    direction = "inflow" if amount >= 0 else "outflow"

    return BankTransaction(
        client_id=client_id,
        user_id=user_id,
        bank_name=bank_name,
        transaction_date=_parse_date(_first(row, ["date", "transaction date", "posting date", "post date"])),
        description=_first(row, ["description", "details", "particulars", "merchant", "remarks"]) or "Bank transaction",
        reference=_first(row, ["reference", "ref", "transaction id", "check no", "cheque no"]),
        amount=abs(amount),
        direction=direction,
        raw_json=row,
    )


@router.post("/import", response_model=BankImportResponse, status_code=201)
async def import_bank_csv(
    client_id: int,
    file: UploadFile = File(...),
    bank_name: str | None = None,
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

    transactions = [
        _transaction_from_row(client_id, current_user.id, row, bank_name)
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]
    db.add_all(transactions)
    db.commit()
    for transaction in transactions:
        db.refresh(transaction)

    return BankImportResponse(imported=len(transactions), transactions=transactions)


@router.get("/transactions", response_model=BankTransactionsResponse)
def list_bank_transactions(
    client_id: int,
    status: str | None = None,
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


def _date_distance_days(left: str | None, right: str | None) -> int | None:
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


def _score_match(transaction: BankTransaction, receipt: Receipt) -> tuple[float, list[str], float | None, bool]:
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

    receipts = db.scalars(
        select(Receipt)
        .options(selectinload(Receipt.data), selectinload(Receipt.line_items))
        .join(ReceiptDataRecord, ReceiptDataRecord.receipt_id == Receipt.id)
        .where(
            Receipt.client_id == client_id,
            Receipt.user_id == current_user.id,
            Receipt.status == "approved",
        )
    ).all()

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
            Reconciliation.receipt_id == receipt.id,
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
    )
    transaction.status = "reconciled"
    db.add(reconciliation)
    db.commit()
    db.refresh(reconciliation)
    return reconciliation


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
