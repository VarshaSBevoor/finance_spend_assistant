from typing import Literal

from pydantic import BaseModel

VendorStatus = Literal["ACTIVE", "INACTIVE", "ON_HOLD"]


class CurrencyTotal(BaseModel):
    currency: str
    total: float
    invoice_count: int


class CurrencyStatusTotal(BaseModel):
    currency: str
    vendor_status: VendorStatus
    total: float
    invoice_count: int


class SummaryResponse(BaseModel):
    invoice_count: int
    spend_by_currency: list[CurrencyTotal]
    spend_by_currency_and_status: list[CurrencyStatusTotal]
    missing_po_count: int
    missing_approver_count: int
