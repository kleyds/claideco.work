from typing import List, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class ReceiptData(BaseModel):
    vendor: Optional[str] = Field(None, description="Merchant or vendor name")
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    currency: Optional[str] = Field(None, description="ISO 4217 currency code (USD, PHP, EUR, ...)")
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: List[LineItem] = []


class ExtractResponse(BaseModel):
    raw_text: str
    data: ReceiptData
