"""True answers for the eval questions, computed straight from the CSV files.

This file does not import anything from app/. It reads the data on its own, so a bug in the
app's loader or query code cannot also hide inside the answer key.
Amounts are net of credit notes, and are never added across currencies.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_frame() -> pd.DataFrame:
    invoices = pd.read_csv(DATA_DIR / "invoices_2025_clean.csv")
    vendors = pd.read_csv(DATA_DIR / "vendor_master.csv")
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    vendor_facts = vendors[["vendor_id", "country", "status"]]
    return invoices.merge(vendor_facts, on="vendor_id", how="left")


def clean(value):
    # A missing PO or approver is a real value, so it becomes None (null in JSON), not NaN.
    if pd.isna(value):
        return None
    return value


def totals_by_currency(frame: pd.DataFrame) -> dict:
    totals = {}
    for currency, group in frame.groupby("currency"):
        totals[currency] = round(float(group["amount"].sum()), 2)
    return totals


def invoice_facts(row: pd.Series) -> dict:
    return {
        "invoice_number": row["invoice_number"],
        "invoice_date": row["invoice_date"].strftime("%Y-%m-%d"),
        "vendor_name": row["vendor_name"],
        "amount": round(float(row["amount"]), 2),
        "currency": row["currency"],
        "po_number": clean(row["po_number"]),
        "approved_by": clean(row["approved_by"]),
    }


def credit_note_count(frame: pd.DataFrame) -> dict:
    credit_notes = frame[frame["amount"] < 0]
    return {"count": len(credit_notes), "invoice_numbers": sorted(credit_notes["invoice_number"])}


def biggest_purchase_per_currency(frame: pd.DataFrame) -> dict:
    result = {}
    for currency, group in frame.groupby("currency"):
        biggest = group.loc[group["amount"].idxmax()]
        result[currency] = invoice_facts(biggest)
    return result


def stellar_purchases(frame: pd.DataFrame) -> dict:
    rows = frame[frame["vendor_name"] == "Stellar Facilities Mgmt"]
    facts = [invoice_facts(row) for _, row in rows.iterrows()]
    missing_po = [fact["invoice_number"] for fact in facts if fact["po_number"] is None]
    return {"count": len(facts), "invoices": facts, "invoices_with_missing_po": missing_po}


def on_hold_totals(frame: pd.DataFrame) -> dict:
    on_hold = frame[frame["status"] == "ON_HOLD"]
    return {"invoice_count": len(on_hold), "totals_by_currency": totals_by_currency(on_hold)}


def on_hold_without_po(frame: pd.DataFrame) -> dict:
    rows = frame[(frame["status"] == "ON_HOLD") & (frame["po_number"].isna())]
    return {"count": len(rows), "invoice_numbers": sorted(rows["invoice_number"])}


def second_quarter_count(frame: pd.DataFrame) -> dict:
    in_quarter = frame[(frame["invoice_date"] >= "2025-04-01") & (frame["invoice_date"] <= "2025-06-30")]
    return {"count": len(in_quarter)}


def latest_invoice(frame: pd.DataFrame) -> dict:
    # More than one invoice can share the latest date, so keep all of them.
    latest_date = frame["invoice_date"].max()
    rows = frame[frame["invoice_date"] == latest_date]
    return {"invoices": [invoice_facts(row) for _, row in rows.iterrows()]}


def uk_vendor_spend(frame: pd.DataFrame) -> dict:
    uk = frame[frame["country"] == "UK"]
    return {"invoice_count": len(uk), "totals_by_currency": totals_by_currency(uk)}


def top_three_vendors_per_currency(frame: pd.DataFrame) -> dict:
    result = {}
    for currency, group in frame.groupby("currency"):
        by_vendor = group.groupby("vendor_name")["amount"].sum().sort_values(ascending=False).head(3)
        result[currency] = [
            {"vendor_name": name, "total": round(float(total), 2)} for name, total in by_vendor.items()
        ]
    return result


def total_spend_overview(frame: pd.DataFrame) -> dict:
    # The mixed sum is the wrong number: it is here so the scorer can spot it in an answer.
    return {
        "totals_by_currency": totals_by_currency(frame),
        "wrong_mixed_currency_sum": round(float(frame["amount"].sum()), 2),
    }


def finance_director_tier_eur(frame: pd.DataFrame) -> dict:
    # Policy 3: 50,000.01 to 250,000 EUR needs the Finance Director. Only EUR can be placed in a tier.
    eur = frame[frame["currency"] == "EUR"]
    in_tier = eur[(eur["amount"] > 50000) & (eur["amount"] <= 250000)]
    other_currency_count = len(frame[frame["currency"] != "EUR"])
    return {
        "eur_invoice_count": len(in_tier),
        "eur_invoice_numbers": sorted(in_tier["invoice_number"]),
        "invoices_in_other_currencies_not_classifiable": other_currency_count,
    }


def biggest_vendor_overall(frame: pd.DataFrame) -> dict:
    by_vendor_mixed = frame.groupby("vendor_name")["amount"].sum().sort_values(ascending=False)
    return {
        "wrong_mixed_currency_leader": by_vendor_mixed.index[0],
        "top_vendor_per_currency": {
            currency: rows[0]["vendor_name"]
            for currency, rows in top_three_vendors_per_currency(frame).items()
        },
    }


def build_truth() -> dict:
    frame = load_frame()
    return {
        "credit_note_count": credit_note_count(frame),
        "biggest_purchase_approver": biggest_purchase_per_currency(frame),
        "stellar_purchases_and_pos": stellar_purchases(frame),
        "on_hold_total": on_hold_totals(frame),
        "on_hold_no_po_and_policy": on_hold_without_po(frame),
        "count_q2": second_quarter_count(frame),
        "latest_invoice": latest_invoice(frame),
        "uk_vendor_spend": uk_vendor_spend(frame),
        "top3_vendors": top_three_vendors_per_currency(frame),
        "total_in_eur": total_spend_overview(frame),
        "finance_director_invoices": finance_director_tier_eur(frame),
        "break_highest_currency": total_spend_overview(frame),
        "break_biggest_vendor_overall": biggest_vendor_overall(frame),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build_truth(), indent=2, default=str))
