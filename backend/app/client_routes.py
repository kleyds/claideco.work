from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Client, User
from app.schemas import (
    ClientCreateRequest,
    ClientPublic,
    ClientsResponse,
    ClientUpdateRequest,
)

router = APIRouter(prefix="/clients", tags=["clients"])

SOFTWARE_OPTIONS = {"quickbooks", "xero", "juantax", "excel", "other"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_software(value: str | None) -> str:
    software = (value or "other").strip().lower()
    if software not in SOFTWARE_OPTIONS:
        raise HTTPException(422, f"software must be one of: {sorted(SOFTWARE_OPTIONS)}")
    return software


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


@router.get("", response_model=ClientsResponse)
def list_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clients = db.scalars(
        select(Client)
        .where(Client.user_id == current_user.id, Client.deleted_at.is_(None))
        .order_by(Client.created_at.desc())
    ).all()
    return ClientsResponse(clients=clients)


@router.post("", response_model=ClientPublic, status_code=201)
def create_client(
    payload: ClientCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = Client(
        user_id=current_user.id,
        name=payload.name.strip(),
        tin=_clean(payload.tin),
        address=_clean(payload.address),
        industry=_clean(payload.industry),
        software=_normalize_software(payload.software),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientPublic)
def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _client_or_404(client_id, current_user.id, db)


@router.put("/{client_id}", response_model=ClientPublic)
def update_client(
    client_id: int,
    payload: ClientUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = _client_or_404(client_id, current_user.id, db)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is not None:
        client.name = updates["name"].strip()
    if "tin" in updates:
        client.tin = _clean(updates["tin"])
    if "address" in updates:
        client.address = _clean(updates["address"])
    if "industry" in updates:
        client.industry = _clean(updates["industry"])
    if "software" in updates and updates["software"] is not None:
        client.software = _normalize_software(updates["software"])

    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = _client_or_404(client_id, current_user.id, db)
    client.deleted_at = datetime.utcnow()
    db.commit()
