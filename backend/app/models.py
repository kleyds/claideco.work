from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    receipts_used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billing_period_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    paymongo_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paymongo_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    clients: Mapped[list["Client"]] = relationship(back_populates="owner")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="owner")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tin: Mapped[str | None] = mapped_column(String(25), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    software: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="clients")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="client")
    bank_transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="client")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_kb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client: Mapped[Client] = relationship(back_populates="receipts")
    owner: Mapped[User] = relationship(back_populates="receipts")
    data: Mapped["ReceiptDataRecord | None"] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        uselist=False,
    )
    line_items: Mapped[list["LineItemRecord"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
    )


class ReceiptDataRecord(Base):
    __tablename__ = "receipt_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), unique=True, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_tin: Mapped[str | None] = mapped_column(String(25), nullable=True)
    or_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    si_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), default="PHP", nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vatable_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    receipt: Mapped[Receipt] = relationship(back_populates="data")


class LineItemRecord(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)

    receipt: Mapped[Receipt] = relationship(back_populates="line_items")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="outflow", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unreconciled", nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    client: Mapped[Client] = relationship(back_populates="bank_transactions")


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True, nullable=False)
    bank_transaction_id: Mapped[int] = mapped_column(ForeignKey("bank_transactions.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="matched", nullable=False)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_2307: Mapped[str] = mapped_column(String(5), default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
