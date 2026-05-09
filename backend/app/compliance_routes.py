from __future__ import annotations

import csv
import io
import re
from collections import OrderedDict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.client_routes import _client_or_404
from app.database import get_db
from app.models import (
    BankTransaction,
    Receipt,
    ReceiptDataRecord,
    Reconciliation,
    User,
)

router = APIRouter(tags=["compliance"])


_QUARTER_PATTERN = re.compile(r"^(\d{4})-Q([1-4])$")
_MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _quarter_bounds(quarter: str) -> tuple[str, str, int, int]:
    match = _QUARTER_PATTERN.match(quarter)
    if not match:
        raise HTTPException(422, "quarter must be in YYYY-Qn form (e.g., 2026-Q1)")
    year = int(match.group(1))
    qnum = int(match.group(2))
    start_month = (qnum - 1) * 3 + 1
    end_month = start_month + 2
    start = date(year, start_month, 1).isoformat()
    if end_month == 12:
        end = date(year, 12, 31).isoformat()
    else:
        end = date(year, end_month + 1, 1).fromordinal(date(year, end_month + 1, 1).toordinal() - 1).isoformat()
    return start, end, year, qnum


def _month_bounds(month: str) -> tuple[str, str]:
    match = _MONTH_PATTERN.match(month)
    if not match:
        raise HTTPException(422, "month must be in YYYY-MM form")
    year = int(match.group(1))
    mnum = int(match.group(2))
    start = date(year, mnum, 1).isoformat()
    if mnum == 12:
        end = date(year, 12, 31).isoformat()
    else:
        end = date(year, mnum + 1, 1).fromordinal(date(year, mnum + 1, 1).toordinal() - 1).isoformat()
    return start, end


def _csv_response(filename: str, headers: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _approved_purchase_receipts(client_id: int, user_id: int, start: str, end: str):
    return (
        select(Receipt)
        .options(selectinload(Receipt.data))
        .join(ReceiptDataRecord, ReceiptDataRecord.receipt_id == Receipt.id)
        .where(
            Receipt.client_id == client_id,
            Receipt.user_id == user_id,
            Receipt.status == "approved",
            ReceiptDataRecord.date >= start,
            ReceiptDataRecord.date <= end,
        )
        .order_by(ReceiptDataRecord.date.asc(), Receipt.id.asc())
    )


@router.get("/clients/{client_id}/exports/slsp")
def export_slsp(
    client_id: int,
    quarter: str = Query(..., description="YYYY-Qn"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summary List of Purchases (SLSP) — aggregates approved expense receipts
    per supplier (vendor TIN) for the BIR quarter. Format follows the spirit of
    BIR's RELIEF SLSP (Schedule 3, Purchases): one row per supplier with
    grouped exempt/zero-rated/taxable/services breakdown.
    """
    _client_or_404(client_id, current_user.id, db)
    start, end, year, qnum = _quarter_bounds(quarter)

    receipts = db.scalars(_approved_purchase_receipts(client_id, current_user.id, start, end)).all()

    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for receipt in receipts:
        data = receipt.data
        if not data:
            continue
        tin = (data.vendor_tin or "").strip() or "NO-TIN"
        key = f"{tin}|{(data.vendor or '').strip().lower()}"
        bucket = grouped.setdefault(
            key,
            {
                "vendor_tin": tin if tin != "NO-TIN" else "",
                "vendor": data.vendor or "",
                "exempt": 0.0,
                "zero_rated": 0.0,
                "vatable": 0.0,
                "vat": 0.0,
                "services": 0.0,
                "gross": 0.0,
                "count": 0,
            },
        )
        total = data.total or 0.0
        vatable = data.vatable_amount or 0.0
        vat = data.vat_amount or 0.0
        vat_type = (data.vat_type or "").lower()
        doc_type = (data.doc_type or "").lower()

        if "exempt" in vat_type:
            bucket["exempt"] += total
        elif "zero" in vat_type:
            bucket["zero_rated"] += total
        else:
            bucket["vatable"] += vatable or (total - vat)
            bucket["vat"] += vat

        if "service" in doc_type or "official receipt" in doc_type or doc_type == "or":
            bucket["services"] += total

        bucket["gross"] += total
        bucket["count"] += 1

    headers = [
        "Quarter",
        "Supplier TIN",
        "Supplier Name",
        "Receipt Count",
        "Exempt Purchases",
        "Zero-Rated Purchases",
        "Taxable Net (VATable)",
        "Input VAT",
        "Services Subtotal",
        "Gross Total",
    ]
    rows = [
        [
            f"{year}-Q{qnum}",
            bucket["vendor_tin"],
            bucket["vendor"],
            bucket["count"],
            round(bucket["exempt"], 2),
            round(bucket["zero_rated"], 2),
            round(bucket["vatable"], 2),
            round(bucket["vat"], 2),
            round(bucket["services"], 2),
            round(bucket["gross"], 2),
        ]
        for bucket in grouped.values()
    ]

    return _csv_response(f"slsp-client-{client_id}-{year}-Q{qnum}.csv", headers, rows)


@router.get("/clients/{client_id}/exports/sawt")
def export_sawt(
    client_id: int,
    quarter: str = Query(..., description="YYYY-Qn"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summary Alphalist of Withholding Taxes (SAWT) — lists Form 2307s tracked
    against reconciliations in the quarter. Pulls the gross income payment from
    the receipt and computes withheld tax from the bank-vs-receipt variance.
    """
    _client_or_404(client_id, current_user.id, db)
    start, end, year, qnum = _quarter_bounds(quarter)

    statement = (
        select(Reconciliation)
        .options(
            selectinload(Reconciliation.receipt).selectinload(Receipt.data),
            selectinload(Reconciliation.bank_transaction),
        )
        .join(BankTransaction, BankTransaction.id == Reconciliation.bank_transaction_id)
        .where(
            Reconciliation.client_id == client_id,
            Reconciliation.user_id == current_user.id,
            Reconciliation.requires_2307 == "true",
            BankTransaction.transaction_date >= start,
            BankTransaction.transaction_date <= end,
        )
        .order_by(BankTransaction.transaction_date.asc())
    )

    reconciliations = db.scalars(statement).all()

    headers = [
        "Quarter",
        "Date Paid",
        "Payee TIN",
        "Payee Name",
        "Reference (OR/SI)",
        "Gross Income",
        "Tax Withheld",
        "ATC (estimated)",
        "Form 2307 Status",
        "Form 2307 Filename",
    ]
    rows = []
    for reconciliation in reconciliations:
        receipt = reconciliation.receipt
        bank_transaction = reconciliation.bank_transaction
        data = receipt.data if receipt else None
        gross = (data.total if data else None) or 0.0
        paid = bank_transaction.amount if bank_transaction else 0.0
        withheld = round(max(0.0, gross - paid), 2)
        atc = ""
        if gross > 0:
            ratio = round((gross - paid) / gross, 2)
            if ratio == 0.01:
                atc = "WC158 (1%)"
            elif ratio == 0.02:
                atc = "WC160 (2%)"
        rows.append(
            [
                f"{year}-Q{qnum}",
                bank_transaction.transaction_date if bank_transaction else "",
                (data.vendor_tin if data else "") or "",
                (data.vendor if data else "") or "",
                (data.or_number or data.si_number) if data else "",
                round(gross, 2),
                withheld,
                atc,
                reconciliation.form_2307_status,
                reconciliation.form_2307_original_name or "",
            ]
        )

    return _csv_response(f"sawt-client-{client_id}-{year}-Q{qnum}.csv", headers, rows)


@router.get("/clients/{client_id}/exports/journal")
def export_4col_journal(
    client_id: int,
    month: str = Query(..., description="YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """4-column journal — Date, Particulars, Debit, Credit.

    Each approved expense receipt produces a debit row (categorized account)
    and a credit row (Cash/Accounts Payable, or the matched bank transaction's
    description when reconciled).
    """
    _client_or_404(client_id, current_user.id, db)
    start, end = _month_bounds(month)

    receipts = db.scalars(_approved_purchase_receipts(client_id, current_user.id, start, end)).all()
    receipt_ids = [receipt.id for receipt in receipts]

    reconciliation_by_receipt: dict[int, Reconciliation] = {}
    if receipt_ids:
        reconciliation_rows = db.scalars(
            select(Reconciliation)
            .options(selectinload(Reconciliation.bank_transaction))
            .where(
                Reconciliation.client_id == client_id,
                Reconciliation.user_id == current_user.id,
                Reconciliation.receipt_id.in_(receipt_ids),
            )
        ).all()
        for row in reconciliation_rows:
            reconciliation_by_receipt[row.receipt_id] = row

    headers = ["Date", "Particulars", "PR", "Debit", "Credit"]
    rows: list[list] = []
    for receipt in receipts:
        data = receipt.data
        if not data:
            continue
        total = data.total or 0.0
        if total == 0:
            continue
        reference = data.or_number or data.si_number or f"R#{receipt.id}"
        vendor = data.vendor or "Vendor"
        debit_account = "Uncategorized Expense"
        if data.vat_amount and data.vat_amount > 0:
            debit_account = "Purchases / Expense"

        reconciliation = reconciliation_by_receipt.get(receipt.id)
        bank_transaction = reconciliation.bank_transaction if reconciliation else None
        credit_account = "Cash" if bank_transaction else "Accounts Payable"
        if bank_transaction and bank_transaction.bank_name:
            credit_account = f"Cash in Bank — {bank_transaction.bank_name}"

        if data.vat_amount and data.vat_amount > 0:
            rows.append([data.date or "", f"{vendor} ({reference})", "", round(data.vatable_amount or 0.0, 2), ""])
            rows.append(["", "Input VAT", "", round(data.vat_amount or 0.0, 2), ""])
        else:
            rows.append([data.date or "", f"{vendor} ({reference})", "", round(total, 2), ""])

        rows.append(["", f"  {credit_account}", "", "", round(total, 2)])
        rows.append(["", "", "", "", ""])

    return _csv_response(f"journal-client-{client_id}-{month}.csv", headers, rows)


def _add_days(reference: date, days: int) -> date:
    return date.fromordinal(reference.toordinal() + days)


def _next_month_start(reference: date) -> date:
    if reference.month == 12:
        return date(reference.year + 1, 1, 1)
    return date(reference.year, reference.month + 1, 1)


@router.get("/clients/{client_id}/compliance/deadlines")
def list_bir_deadlines(
    client_id: int,
    as_of: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upcoming BIR filing deadlines for the next ~120 days, computed from a
    static schedule. Useful for surfacing 'next things due' on the dashboard.
    """
    _client_or_404(client_id, current_user.id, db)

    if as_of:
        try:
            today = date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(422, "as_of must be YYYY-MM-DD") from exc
    else:
        today = date.today()

    horizon = _add_days(today, 120)
    upcoming = _bir_deadlines_between(today, horizon)
    return {"as_of": today.isoformat(), "deadlines": upcoming}


def _previous_month(reference: date) -> tuple[int, int]:
    if reference.month == 1:
        return reference.year - 1, 12
    return reference.year, reference.month - 1


def _quarter_for(reference: date) -> tuple[int, int, date]:
    qnum = (reference.month - 1) // 3 + 1
    end_month = qnum * 3
    end_day = 31 if end_month in {3, 12} else 30
    return reference.year, qnum, date(reference.year, end_month, end_day)


def _bir_deadlines_between(start: date, end: date) -> list[dict]:
    candidates: list[dict] = []

    # Walk months from current month to end horizon to seed monthly deadlines.
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        prev_year, prev_month = _previous_month(cursor)
        covers_month = f"{prev_year}-{prev_month:02d}"
        candidates.append(
            {
                "form": "1601-C",
                "label": "Monthly Withholding (Compensation)",
                "due": date(cursor.year, cursor.month, 10).isoformat(),
                "covers": covers_month,
            }
        )
        candidates.append(
            {
                "form": "2550M",
                "label": "Monthly VAT Return",
                "due": date(cursor.year, cursor.month, 20).isoformat(),
                "covers": covers_month,
            }
        )
        cursor = _next_month_start(cursor)

    # Quarterly deadlines for current and next quarter.
    seen_quarters: set[tuple[int, int]] = set()
    cursor = start
    for _ in range(3):
        qyear, qnum, q_end = _quarter_for(cursor)
        if (qyear, qnum) not in seen_quarters:
            seen_quarters.add((qyear, qnum))
            month_after = _next_month_start(q_end)
            eom_after = date.fromordinal(_next_month_start(month_after).toordinal() - 1)
            candidates.extend(
                [
                    {
                        "form": "2550Q + SLSP",
                        "label": "Quarterly VAT Return + Summary List of Purchases",
                        "due": date(month_after.year, month_after.month, 25).isoformat(),
                        "covers": f"{qyear}-Q{qnum}",
                    },
                    {
                        "form": "1601-EQ + QAP",
                        "label": "Quarterly Expanded Withholding",
                        "due": eom_after.isoformat(),
                        "covers": f"{qyear}-Q{qnum}",
                    },
                    {
                        "form": "1701Q / 1702Q + SAWT",
                        "label": "Quarterly Income Tax Return + SAWT",
                        "due": _add_days(q_end, 60).isoformat(),
                        "covers": f"{qyear}-Q{qnum}",
                    },
                ]
            )
        cursor = _add_days(q_end, 1)

    visible = [item for item in candidates if start.isoformat() <= item["due"] <= end.isoformat()]
    visible.sort(key=lambda item: item["due"])
    return visible
