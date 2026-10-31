import pandas as pd

from app.schemas import CurrencyStatusTotal, CurrencyTotal, SummaryResponse


def build_summary(invoices: pd.DataFrame) -> SummaryResponse:
    """Spend overview. Amounts are never added across currencies."""
    # Each groupby gives one row per group, with the sum and the invoice count.
    by_currency = invoices.groupby("currency")["amount"].agg(["sum", "count"])
    by_currency_status = invoices.groupby(["currency", "status"])["amount"].agg(["sum", "count"])

    return SummaryResponse(
        invoice_count=len(invoices),
        # round() hides float noise such as 0.30000000000000004.
        # int() turns numpy integers into plain ints for Pydantic.
        spend_by_currency=[
            CurrencyTotal(currency=currency, total=round(row["sum"], 2), invoice_count=int(row["count"]))
            for currency, row in by_currency.iterrows()
        ],
        spend_by_currency_and_status=[
            CurrencyStatusTotal(
                currency=currency,
                vendor_status=status,
                total=round(row["sum"], 2),
                invoice_count=int(row["count"]),
            )
            for (currency, status), row in by_currency_status.iterrows()
        ],
        # Missing PO and approver are real values, so they are counted, not dropped.
        missing_po_count=int(invoices["po_number"].isna().sum()),
        missing_approver_count=int(invoices["approved_by"].isna().sum()),
    )
