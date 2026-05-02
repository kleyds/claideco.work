from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class ReceiptData(BaseModel):
    vendor: Optional[str] = Field(None, description="Merchant or vendor name")
    vendor_tin: Optional[str] = Field(None, description="Philippine TIN, if visible")
    or_number: Optional[str] = Field(None, description="Official Receipt number")
    si_number: Optional[str] = Field(None, description="Sales Invoice number")
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    currency: Optional[str] = Field("PHP", description="ISO 4217 currency code")
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    vat_type: Optional[str] = Field(
        None,
        description="One of: vatable, zero_rated, exempt, non_vat",
    )
    vatable_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    total: Optional[float] = None
    doc_type: Optional[str] = Field(
        None,
        description="One of: official_receipt, sales_invoice, gcash, maya, bank_statement, other",
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    line_items: List[LineItem] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    raw_text: str
    data: ReceiptData


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    plan: str

    model_config = {"from_attributes": True}


class AuthRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MeResponse(BaseModel):
    user: UserPublic


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    tin: Optional[str] = Field(None, max_length=25)
    address: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    software: str = Field("other", max_length=50)


class ClientCreateRequest(ClientBase):
    pass


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tin: Optional[str] = Field(None, max_length=25)
    address: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    software: Optional[str] = Field(None, max_length=50)


class ClientPublic(ClientBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientsResponse(BaseModel):
    clients: List[ClientPublic]


class ClientMetrics(BaseModel):
    client_id: int
    unprocessed_invoices: int = 0
    unreconciled_bank_entries: int = 0
    missing_2307s: int = 0


class ClientMetricsResponse(BaseModel):
    metrics: List[ClientMetrics]


class ReceiptDataPublic(BaseModel):
    vendor: Optional[str] = None
    vendor_tin: Optional[str] = None
    or_number: Optional[str] = None
    si_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = "PHP"
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    vat_type: Optional[str] = None
    vatable_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    total: Optional[float] = None
    doc_type: Optional[str] = None
    confidence: Optional[float] = None

    model_config = {"from_attributes": True}


class ReceiptDataUpdate(BaseModel):
    vendor: Optional[str] = None
    vendor_tin: Optional[str] = None
    or_number: Optional[str] = None
    si_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = "PHP"
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    vat_type: Optional[str] = None
    vatable_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    total: Optional[float] = None
    doc_type: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class LineItemPublic(BaseModel):
    id: int
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None

    model_config = {"from_attributes": True}


class ReceiptPublic(BaseModel):
    id: int
    client_id: int
    user_id: int
    original_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_kb: int
    status: str
    raw_text: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    data: Optional[ReceiptDataPublic] = None
    line_items: List[LineItemPublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReceiptPatchRequest(BaseModel):
    status: Optional[str] = None
    data: Optional[ReceiptDataUpdate] = None
    line_items: Optional[List[LineItem]] = None


class ReceiptUploadItem(BaseModel):
    receipt_id: int
    original_name: Optional[str]
    status: str


class ReceiptUploadResponse(BaseModel):
    receipts: List[ReceiptUploadItem]


class ReceiptsResponse(BaseModel):
    receipts: List[ReceiptPublic]


class BankTransactionPublic(BaseModel):
    id: int
    client_id: int
    user_id: int
    bank_name: Optional[str] = None
    transaction_date: Optional[str] = None
    description: str
    reference: Optional[str] = None
    amount: float
    direction: str
    status: str
    category: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankImportResponse(BaseModel):
    imported: int
    transactions: List[BankTransactionPublic]


class BankTransactionsResponse(BaseModel):
    transactions: List[BankTransactionPublic]


class MatchSuggestion(BaseModel):
    receipt: ReceiptPublic
    score: float
    reasons: List[str]
    withholding_variance: Optional[float] = None
    requires_2307: bool = False


class MatchSuggestionsResponse(BaseModel):
    transaction: BankTransactionPublic
    suggestions: List[MatchSuggestion]


class ReconcileRequest(BaseModel):
    receipt_id: int
    match_score: Optional[float] = None
    requires_2307: bool = False


class ReconciliationPublic(BaseModel):
    id: int
    client_id: int
    user_id: int
    receipt_id: int
    bank_transaction_id: int
    status: str
    match_score: Optional[float] = None
    requires_2307: str
    form_2307_status: str = "missing"
    form_2307_original_name: Optional[str] = None
    form_2307_mime_type: Optional[str] = None
    form_2307_uploaded_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReconciliationDetailPublic(ReconciliationPublic):
    receipt: ReceiptPublic
    bank_transaction: BankTransactionPublic
    has_form_2307_file: bool = False


class ReconciliationsResponse(BaseModel):
    reconciliations: List[ReconciliationDetailPublic]


class Form2307UpdateRequest(BaseModel):
    status: str = Field(pattern=r"^(missing|requested|received|attached)$")


class BulkCategorizeRequest(BaseModel):
    transaction_ids: List[int]
    category: str = Field(min_length=1, max_length=100)


class BulkCategorizeResponse(BaseModel):
    updated: int
    transactions: List[BankTransactionPublic]
