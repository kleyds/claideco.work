from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.client_routes import _client_or_404
from app.database import get_db
from app.models import Client, ClientUploadLink, Receipt, User
from app.receipt_routes import ALLOWED_TYPES, _extension, process_receipt
from app.schemas import (
    PortalInfoResponse,
    ReceiptUploadItem,
    ReceiptUploadResponse,
    UploadLinkCreateRequest,
    UploadLinkPublic,
    UploadLinksResponse,
)

auth_router = APIRouter(tags=["portal-admin"])
public_router = APIRouter(prefix="/portal", tags=["portal-public"])


def _upload_root() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _link_or_404(token: str, db: Session) -> ClientUploadLink:
    link = db.scalar(select(ClientUploadLink).where(ClientUploadLink.token == token))
    if not link:
        raise HTTPException(404, "Upload link not found")
    return link


def _ensure_link_usable(link: ClientUploadLink) -> None:
    if link.revoked_at is not None:
        raise HTTPException(410, "This upload link has been revoked")
    if link.expires_at is not None and link.expires_at < datetime.utcnow():
        raise HTTPException(410, "This upload link has expired")
    if link.max_uploads is not None and link.uploads_count >= link.max_uploads:
        raise HTTPException(429, "This upload link has reached its upload limit")


@auth_router.post(
    "/clients/{client_id}/upload-links",
    response_model=UploadLinkPublic,
    status_code=201,
)
def create_upload_link(
    client_id: int,
    payload: UploadLinkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)
    link = ClientUploadLink(
        client_id=client_id,
        user_id=current_user.id,
        token=_new_token(),
        label=(payload.label or "").strip() or None,
        max_uploads=payload.max_uploads,
        expires_at=expires_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@auth_router.get("/clients/{client_id}/upload-links", response_model=UploadLinksResponse)
def list_upload_links(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    links = db.scalars(
        select(ClientUploadLink)
        .where(
            ClientUploadLink.client_id == client_id,
            ClientUploadLink.user_id == current_user.id,
        )
        .order_by(ClientUploadLink.created_at.desc())
    ).all()
    return UploadLinksResponse(links=links)


@auth_router.delete("/clients/{client_id}/upload-links/{link_id}", status_code=204)
def revoke_upload_link(
    client_id: int,
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _client_or_404(client_id, current_user.id, db)
    link = db.scalar(
        select(ClientUploadLink).where(
            ClientUploadLink.id == link_id,
            ClientUploadLink.client_id == client_id,
            ClientUploadLink.user_id == current_user.id,
        )
    )
    if not link:
        raise HTTPException(404, "Upload link not found")
    if link.revoked_at is None:
        link.revoked_at = datetime.utcnow()
        db.commit()
    return None


@public_router.get("/{token}", response_model=PortalInfoResponse)
def portal_info(token: str, db: Session = Depends(get_db)):
    link = _link_or_404(token, db)
    _ensure_link_usable(link)
    client = db.scalar(select(Client).where(Client.id == link.client_id))
    if not client or client.deleted_at is not None:
        raise HTTPException(410, "This upload link is no longer active")
    remaining: Optional[int] = None
    if link.max_uploads is not None:
        remaining = max(0, link.max_uploads - link.uploads_count)
    return PortalInfoResponse(
        client_name=client.name,
        label=link.label,
        uploads_remaining=remaining,
        expires_at=link.expires_at,
    )


@public_router.post(
    "/{token}/upload",
    response_model=ReceiptUploadResponse,
    status_code=201,
)
async def portal_upload(
    token: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Receipt or invoice files"),
    db: Session = Depends(get_db),
):
    link = _link_or_404(token, db)
    _ensure_link_usable(link)

    client = db.scalar(select(Client).where(Client.id == link.client_id))
    if not client or client.deleted_at is not None:
        raise HTTPException(410, "This upload link is no longer active")

    max_files = int(os.getenv("MAX_FILES_PER_UPLOAD", "50"))
    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    if len(files) > max_files:
        raise HTTPException(400, f"Too many files; max is {max_files}")

    if link.max_uploads is not None:
        remaining = link.max_uploads - link.uploads_count
        if len(files) > remaining:
            raise HTTPException(429, f"Only {remaining} upload(s) remain on this link")

    target_dir = _upload_root() / str(link.user_id) / str(link.client_id)
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
            client_id=link.client_id,
            user_id=link.user_id,
            file_path=str(file_path),
            original_name=file.filename,
            mime_type=file.content_type,
            file_size_kb=max(1, round(len(content) / 1024)),
            status="pending",
        )
        db.add(receipt)
        created.append(receipt)

    link.uploads_count += len(created)
    link.last_used_at = datetime.utcnow()
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
