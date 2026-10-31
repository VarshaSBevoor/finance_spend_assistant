from fastapi.testclient import TestClient

from app.main import app


def test_summary_returns_contract_shape_and_known_totals():
    # The `with` block matters: it runs the app's startup, which loads the data.
    with TestClient(app) as client:
        response = client.get("/summary")

    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "invoice_count",
        "spend_by_currency",
        "spend_by_currency_and_status",
        "missing_po_count",
        "missing_approver_count",
    }
    assert body["invoice_count"] == 140
    assert body["missing_po_count"] == 21
    assert body["missing_approver_count"] == 25

    totals = {row["currency"]: row["total"] for row in body["spend_by_currency"]}
    assert totals == {"EUR": 4493726.12, "GBP": 1182251.02, "USD": 1150445.53}
