from typing import Literal

from pydantic import BaseModel, Field

from app.plan import Route

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


class DataResult(BaseModel):
    rows: list[dict]
    matched_invoice_count: int  # invoices left after the filters, before grouping
    how_computed: str
    # True when a limit cut the result separately for each currency (a "top N").
    limit_per_currency: bool = False


class AskRequest(BaseModel):
    # A length limit keeps one request from sending a huge prompt to the model.
    question: str = Field(min_length=1, max_length=500)


class PolicyEvidence(BaseModel):
    section_id: str
    text: str  # exact text from the policy file


class Evidence(BaseModel):
    policy: list[PolicyEvidence]
    data: DataResult | None


class Check(BaseModel):
    name: str
    passed: bool
    detail: str


class Meta(BaseModel):
    backend: str
    model: str
    prompt_version: str
    stub: bool
    fallback_used: bool


class AskResponse(BaseModel):
    answer: str
    declined: bool  # True when the answer is a reason for not answering
    route: Route
    evidence: Evidence
    checks: list[Check]
    meta: Meta
