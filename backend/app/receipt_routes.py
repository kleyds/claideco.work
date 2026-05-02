import csv
import io
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, user_from_token
from app.database import SessionLocal, get_db
from app.extract import extract_receipt
from app.models import Client, LineItemRecord, Receipt, ReceiptDataRecord, User
from app.ocr import image_to_text
from app.schemas import (
    ReceiptPatchRequest,
    ReceiptPublic,
    ReceiptsResponse,
    ReceiptUploadItem,
    ReceiptUploadResponse,
)

router = APIRouter(tags=["receipts"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_TYPES = IMAGE_TYPES | {"application/pdf"}


def _upload_root() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()


def _client_or_404(client_id: int, user_id: int, db: Session) -> Client:
    client = db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.user_id == user_id,
            Client.deleted_at.is_(None),
        )
    )
    if not client:
        raise HTTPException(404, "Client not found")
    return client


def _receipt_or_404(receipt_id: int, user_id: int, db: Session) -> Receipt:
    receipt = db.scalar(
        select(Receipt)
        .options(selectinload(Receipt.data), selectinload(Receipt.line_items))
        .where(Receipt.id == receipt_id, Receipt.user_id == user_id)
    )
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    return receipt


def _extension(filename: str | None, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        return suffix
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(content_type or "", "")


def _next_month(month: str) -> str:
    year, month_number = [int(part) for part in month.split("-")]
    if month_number == 12:
        return f"{year + 1}-01-01"
    return f"{year}-{month_number + 1:02d}-01"


def _receipt_statement(
    client_id: int,
    user_id: int,
    status: str | None = None,
    month: str | None = None,
    vendor: str | None = None,
    doc_type: str | None = None,
    vat_type: str | None = None,
    min_total: float | None = None,
    max_total: float | None = None,
):
    statement = (
        select(Receipt)
        .options(selectinload(Receipt.data), selectinload(Receipt.line_items))
        .where(Receipt.client_id == client_id, Receipt.user_id == user_id)
    )

    joined_data = False

    def with_data_join():
        nonlocal statement, joined_data
        if not joined_data:
            statement = statement.join(ReceiptDataRecord, ReceiptDataRecord.receipt_id == Receipt.id)
            joined_data = True

    if status:
        statement = statement.where(Receipt.status == status)
    if month:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.date >= f"{month}-01", ReceiptDataRecord.date < _next_month(month))
    if vendor:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.vendor.ilike(f"%{vendor}%"))
    if doc_type:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.doc_type == doc_type)
    if vat_type:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.vat_type == vat_type)
    if min_total is not None:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.total >= min_total)
    if max_total is not None:
        with_data_join()
        statement = statement.where(ReceiptDataRecord.total <= max_total)

    return statement


def _write_csv(headers: list[str], rows: list[list[object | None]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _receipt_reference(receipt: Receipt) -> str:
    data = receipt.data
    if not data:
        return ""
    return data.or_number or data.si_number or ""


def _csv_for_receipts(receipts: list[Receipt], export_format: str) -> str:
    if export_format == "qbo":
        headers = ["Date", "Description", "Account", "Debit", "Credit", "Memo", "Name"]
        rows = [
            [
                receipt.data.date if receipt.data else "",
                receipt.data.vendor if receipt.data else receipt.original_name,
                "Uncategorized Expense",
                receipt.data.total if receipt.data else "",
                "",
                _receipt_reference(receipt),
                receipt.data.vendor if receipt.data else "",
            ]
            for receipt in receipts
        ]
        return _write_csv(headers, rows)

    if export_format == "xero":
        headers = ["Date", "Amount", "Payee", "Description", "Reference", "Account Code"]
        rows = [
            [
                receipt.data.date if receipt.data else "",
                receipt.data.total if receipt.data else "",
                receipt.data.vendor if receipt.data else "",
                receipt.original_name or f"Receipt #{receipt.id}",
                _receipt_reference(receipt),
                "",
            ]
            for receipt in receipts
        ]
        return _write_csv(headers, rows)

    headers = [
        "receipt_id",
        "date",
        "vendor",
        "vendor_tin",
        "or_number",
        "si_number",
        "currency",
        "subtotal",
        "tax",
        "vat_type",
        "vatable_amount",
        "vat_amount",
        "total",
        "doc_type",
        "confidence",
        "original_name",
    ]
    rows = [
        [
            receipt.id,
            receipt.data.date if receipt.data else "",
            receipt.data.vendor if receipt.data else "",
            receipt.data.vendor_tin if receipt.data else "",
            receipt.data.or_number if receipt.data else "",
            receipt.data.si_number if receipt.data else "",
            receipt.data.currency if receipt.data else "PHP",
            receipt.data.subtotal if receipt.data else "",
            receipt.data.tax if receipt.data else "",
            receipt.data.vat_type if receipt.data else "",
            receipt.data.vatable_amount if receipt.data else "",
            receipt.data.vat_amount if receipt.data else "",
            receipt.data.total if receipt.data else "",
            receipt.data.doc_type if receipt.data else "",
            receipt.data.confidence if receipt.data else "",
            receipt.original_name,
        ]
        for receipt in receipts
    ]
    return _write_csv(headers, rows)


def _persist_extracted_data(db: Session, receipt: Receipt, raw_text: str) -> None:
    extracted = extract_receipt(raw_text)
    payload = extracted.model_dump()
    line_items = payload.pop("line_items", [])

    receipt.data = ReceiptDataRecord(
        receipt_id=receipt.id,
        raw_json=extracted.model_dump(),
        **payload,
    )
    receipt.line_items = [
        LineItemRecord(
            receipt_id=receipt.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total=item.total,
        )
        for item in extracted.line_items
    ]


def process_receipt(receipt_id: int) -> None:
    db = SessionLocal()
    try:
        receipt = db.get(Receipt, receipt_id)
        if not receipt:
            return

        receipt.status = "processing"
        receipt.error_message = None
        db.commit()

        if receipt.mime_type not in IMAGE_TYPES:
            receipt.status = "error"
            receipt.error_message = "PDF extraction is not implemented yet; file is stored for later processing."
            receipt.processed_at = datetime.utcnow()
            db.commit()
            return

        with open(receipt.file_path, "rb") as file:
            content = file.read()

        raw_text = image_to_text(content)
        receipt.raw_text = raw_text
        _persist_extracted_data(db, receipt, raw_text)
        receipt.status = "done"
        receipt.processed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        receipt = db.get(Receipt, receipt_id)
        if receipt:
            receipt.status = "error"
            receipt.error_message = str(exc)
            receipt.processed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.post(
    "/clients/{client_id}/receipts/upload",
    response_model=ReceiptUploadResponse,
    status_code=201,
)
async def upload_receipts(
    client_id: int,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Receipt, invoice, or bank document files"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)

    max_files = int(os.getenv("MAX_FILES_PER_UPLOAD", "50"))
    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    if len(files) > max_files:
        raise HTTPException(400, f"Too many files; max is {max_files}")

    target_dir = _upload_root() / str(current_user.id) / str(client_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    created: list[Receipt] = []
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, f"Unsupported file type: {file.content_type}")

        content = await file.read()
        if len(content) > max_mb * 1024 * 1024:
            raise HTTPException(413, f"{file.filename or 'File'} is too large (max {max_mb} MB)")

        ext = _extension(file.filename, file.content_type)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = target_dir / stored_name
        file_path.write_bytes(content)

        receipt = Receipt(
            client_id=client_id,
            user_id=current_user.id,
            file_path=str(file_path),
            original_name=file.filename,
            mime_type=file.content_type,
            file_size_kb=max(1, round(len(content) / 1024)),
            status="pending",
        )
        db.add(receipt)
        created.append(receipt)

    db.commit()
    for receipt in created:
        db.refresh(receipt)
        background_tasks.add_task(process_receipt, receipt.id)

    return ReceiptUploadResponse(
        receipts=[
            ReceiptUploadItem(
                receipt_id=receipt.id,
                original_name=receipt.original_name,
                status=receipt.status,
            )
            for receipt in created
        ]
    )


@router.get("/clients/{client_id}/receipts", response_model=ReceiptsResponse)
def list_receipts(
    client_id: int,
    status: str | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    vendor: str | None = None,
    doc_type: str | None = None,
    vat_type: str | None = None,
    min_total: float | None = None,
    max_total: float | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    statement = _receipt_statement(
        client_id=client_id,
        user_id=current_user.id,
        status=status,
        month=month,
        vendor=vendor,
        doc_type=doc_type,
        vat_type=vat_type,
        min_total=min_total,
        max_total=max_total,
    )
    receipts = db.scalars(statement.order_by(Receipt.created_at.desc())).all()
    return ReceiptsResponse(receipts=receipts)


@router.get("/clients/{client_id}/export")
def export_receipts(
    client_id: int,
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    format: str = Query("generic", pattern=r"^(generic|qbo|xero)$"),
    vendor: str | None = None,
    doc_type: str | None = None,
    vat_type: str | None = None,
    min_total: float | None = None,
    max_total: float | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    statement = _receipt_statement(
        client_id=client_id,
        user_id=current_user.id,
        status="approved",
        month=month,
        vendor=vendor,
        doc_type=doc_type,
        vat_type=vat_type,
        min_total=min_total,
        max_total=max_total,
    )
    receipts = db.scalars(statement.order_by(Receipt.created_at.asc())).all()
    csv_text = _csv_for_receipts(receipts, format)
    filename_month = month or "all"
    filename = f"pesobooks-client-{client_id}-{format}-{filename_month}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/clients/{client_id}/receipts/queue", response_model=ReceiptsResponse)
def review_queue(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    receipts = db.scalars(
        select(Receipt)
        .options(selectinload(Receipt.data), selectinload(Receipt.line_items))
        .where(
            Receipt.client_id == client_id,
            Receipt.user_id == current_user.id,
            Receipt.status.in_(["pending", "processing", "done", "error"]),
        )
        .order_by(Receipt.created_at.asc())
    ).all()
    return ReceiptsResponse(receipts=receipts)


@router.get("/receipts/{receipt_id}", response_model=ReceiptPublic)
def get_receipt(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _receipt_or_404(receipt_id, current_user.id, db)


@router.get("/receipts/{receipt_id}/file")
def get_receipt_file(
    receipt_id: int,
    token: str,
    db: Session = Depends(get_db),
):
    current_user = user_from_token(token, db)
    receipt = _receipt_or_404(receipt_id, current_user.id, db)
    path = Path(receipt.file_path)
    if not path.exists():
        raise HTTPException(404, "Receipt file not found")
    return FileResponse(path, media_type=receipt.mime_type, filename=receipt.original_name)


@router.patch("/receipts/{receipt_id}", response_model=ReceiptPublic)
def update_receipt(
    receipt_id: int,
    payload: ReceiptPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receipt = _receipt_or_404(receipt_id, current_user.id, db)

    if payload.status is not None:
        if payload.status not in {"pending", "processing", "done", "error", "approved", "rejected"}:
            raise HTTPException(422, "Invalid receipt status")
        receipt.status = payload.status
        if payload.status in {"done", "approved", "rejected", "error"}:
            receipt.processed_at = datetime.utcnow()

    if payload.data is not None:
        data_payload = payload.data.model_dump()
        if receipt.data is None:
            receipt.data = ReceiptDataRecord(receipt_id=receipt.id, raw_json=data_payload)
        for key, value in data_payload.items():
            setattr(receipt.data, key, value)
        receipt.data.raw_json = data_payload

    if payload.line_items is not None:
        receipt.line_items = [
            LineItemRecord(
                receipt_id=receipt.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total,
            )
            for item in payload.line_items
        ]

    db.commit()
    db.refresh(receipt)
    return _receipt_or_404(receipt.id, current_user.id, db)
