from app.llm import evidence_as_text
from app.schemas import DataResult, Evidence


def test_rows_with_a_currency_are_grouped_under_a_heading_for_each_currency():
    evidence = Evidence(
        policy=[],
        data=DataResult(
            rows=[
                {"vendor_name": "A", "currency": "EUR", "total_amount": 300.0},
                {"vendor_name": "B", "currency": "EUR", "total_amount": 200.0},
                {"vendor_name": "C", "currency": "GBP", "total_amount": 70.0},
            ],
            matched_invoice_count=5,
            how_computed="Limit of 2 applied per currency.",
            limit_per_currency=True,
        ),
    )

    lines = evidence_as_text(evidence).splitlines()

    assert lines.index("Currency EUR:") < lines.index("Currency GBP:")
    assert lines.count("Currency EUR:") == 1  # one heading per currency, not per row
    assert lines[lines.index("Currency GBP:") + 1].startswith("- vendor_name: C")
