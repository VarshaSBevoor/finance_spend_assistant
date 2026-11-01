import json

import pandas as pd

from app.execute import run_data_query
from app.plan import DataQuery

# Eight invoices, hand-made. Missing PO: INV-2 and INV-6. Missing approver: INV-3.
INVOICES = pd.DataFrame(
    {
        "invoice_number": ["INV-1", "INV-2", "INV-3", "INV-4", "INV-5", "INV-6", "INV-7", "INV-8"],
        "invoice_date": pd.to_datetime(
            ["2025-01-10", "2025-02-10", "2025-03-10", "2025-04-10", "2025-05-10", "2025-06-10", "2025-07-10", "2025-08-10"]
        ),
        "vendor_name": ["Alpha", "Alpha", "Beta", "Gamma", "Alpha", "Beta", "Gamma", "Gamma"],
        "amount": [100.00, 50.00, 300.00, 200.00, 70.00, 10.00, 40.00, 900.00],
        "currency": ["EUR", "EUR", "EUR", "EUR", "GBP", "GBP", "GBP", "USD"],
        "po_number": ["PO-1", None, "PO-3", "PO-4", "PO-5", None, "PO-7", "PO-8"],
        "approved_by": ["a", "a", None, "b", "a", "b", "b", "a"],
        "country": ["Spain", "Spain", "France", "Spain", "Spain", "France", "Spain", "Spain"],
        "status": ["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "ACTIVE", "ON_HOLD", "INACTIVE", "ACTIVE"],
    }
)


def make_query(filters=None, group_by=None, aggregate="sum", sort=None, limit=None) -> DataQuery:
    return DataQuery.model_validate(
        {"filters": filters or [], "group_by": group_by or [], "aggregate": aggregate, "sort": sort, "limit": limit}
    )


def test_sum_with_filter_groups_by_vendor_and_currency_sorted_within_currency():
    query = make_query(
        filters=[{"column": "country", "op": "eq", "value": "Spain"}],
        group_by=["vendor_name", "currency"],
        sort="desc",
    )

    result = run_data_query(INVOICES, query)

    # Spain: INV-1, 2, 4, 5, 7, 8. Rows are ordered by currency, then by total, largest first.
    assert result.rows == [
        {"vendor_name": "Gamma", "currency": "EUR", "total_amount": 200.0, "invoice_count": 1},
        {"vendor_name": "Alpha", "currency": "EUR", "total_amount": 150.0, "invoice_count": 2},
        {"vendor_name": "Alpha", "currency": "GBP", "total_amount": 70.0, "invoice_count": 1},
        {"vendor_name": "Gamma", "currency": "GBP", "total_amount": 40.0, "invoice_count": 1},
        {"vendor_name": "Gamma", "currency": "USD", "total_amount": 900.0, "invoice_count": 1},
    ]
    assert result.matched_invoice_count == 6


def test_limit_applies_per_currency_and_the_explanation_says_so():
    query = make_query(group_by=["vendor_name", "currency"], sort="desc", limit=1)

    result = run_data_query(INVOICES, query)

    # EUR: Alpha 150, Beta 300, Gamma 200. GBP: Alpha 70, Beta 10, Gamma 40. USD: Gamma 900.
    assert result.rows == [
        {"vendor_name": "Beta", "currency": "EUR", "total_amount": 300.0, "invoice_count": 1},
        {"vendor_name": "Alpha", "currency": "GBP", "total_amount": 70.0, "invoice_count": 1},
        {"vendor_name": "Gamma", "currency": "USD", "total_amount": 900.0, "invoice_count": 1},
    ]
    assert result.matched_invoice_count == 8
    assert "per currency" in result.how_computed
    assert result.limit_per_currency


def test_count_of_missing_po_is_a_single_row():
    query = make_query(filters=[{"column": "po_number", "op": "is_null"}], aggregate="count")

    result = run_data_query(INVOICES, query)

    assert result.rows == [{"invoice_count": 2}]  # INV-2 and INV-6
    assert result.matched_invoice_count == 2


def test_rows_are_json_safe_with_missing_values_and_dates():
    query = make_query(filters=[{"column": "po_number", "op": "is_null"}], aggregate="rows", sort="asc")

    result = run_data_query(INVOICES, query)

    # Ordered by currency, then amount ascending: INV-2 (EUR 50), INV-6 (GBP 10).
    assert [row["invoice_number"] for row in result.rows] == ["INV-2", "INV-6"]
    # Only the core columns plus the one the question filtered on, not all of them.
    assert list(result.rows[0]) == ["invoice_number", "invoice_date", "vendor_name", "amount", "currency", "po_number"]
    assert result.rows[0]["po_number"] is None  # missing stays None, not NaN
    assert result.rows[0]["invoice_date"] == "2025-02-10"  # a plain string, not a Timestamp
    json.dumps(result.rows)  # raises an error if anything is not JSON-safe


def test_no_matching_invoices_gives_empty_rows_and_zero():
    query = make_query(filters=[{"column": "country", "op": "eq", "value": "Germany"}])

    result = run_data_query(INVOICES, query)

    assert result.rows == []
    assert result.matched_invoice_count == 0
    assert result.how_computed  # still explains what was done


def test_a_missing_value_is_its_own_group_when_grouping():
    query = make_query(group_by=["approved_by"], aggregate="count")

    result = run_data_query(INVOICES, query)

    # INV-3 has no approver. It must not vanish from the counts.
    counts = {row["approved_by"]: row["invoice_count"] for row in result.rows}
    assert counts == {"a": 4, "b": 3, None: 1}
