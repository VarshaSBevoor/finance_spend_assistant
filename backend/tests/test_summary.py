import pandas as pd

from app.summary import build_summary

# Hand calculation for this frame:
#   EUR total       100.00 + 50.50 - 20.00 = 130.50   (3 invoices, one is a credit note)
#   EUR / ACTIVE    100.00 + 50.50         = 150.50   (2 invoices)
#   EUR / INACTIVE  -20.00                            (1 invoice)
#   GBP total       0.10 + 0.20            = 0.30     (2 invoices, plain floats give 0.30000000000000004)
#   missing PO: 1 (row 2). missing approver: 1 (row 3).
SMALL_FRAME = pd.DataFrame(
    {
        "currency": ["EUR", "EUR", "EUR", "GBP", "GBP"],
        "status": ["ACTIVE", "ACTIVE", "INACTIVE", "ACTIVE", "ACTIVE"],
        "amount": [100.00, 50.50, -20.00, 0.10, 0.20],
        "po_number": ["PO-1", None, "PO-3", "PO-4", "PO-5"],
        "approved_by": ["a.one", "a.one", None, "b.two", "b.two"],
    }
)


def test_totals_match_hand_calculation_and_stay_per_currency():
    summary = build_summary(SMALL_FRAME)

    totals = {row.currency: (row.total, row.invoice_count) for row in summary.spend_by_currency}
    assert totals == {"EUR": (130.50, 3), "GBP": (0.30, 2)}

    by_status = {
        (row.currency, row.vendor_status): (row.total, row.invoice_count)
        for row in summary.spend_by_currency_and_status
    }
    assert by_status == {
        ("EUR", "ACTIVE"): (150.50, 2),
        ("EUR", "INACTIVE"): (-20.00, 1),
        ("GBP", "ACTIVE"): (0.30, 2),
    }
    assert summary.invoice_count == 5


def test_missing_po_and_approver_are_counted_not_dropped():
    summary = build_summary(SMALL_FRAME)

    assert summary.missing_po_count == 1
    assert summary.missing_approver_count == 1
    assert summary.invoice_count == 5
