from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_invoices(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Invoices joined with vendor country, category and status.

    Blank po_number and approved_by cells become NaN. They are real values
    (missing PO, missing approver), so nothing fills them in.
    """
    invoices = pd.read_csv(
        data_dir / "invoices_2025_clean.csv",
        parse_dates=["invoice_date"],
        keep_default_na=False,
        na_values=[""],
    )
    vendors = pd.read_csv(data_dir / "vendor_master.csv")

    merged = invoices.merge(
        vendors[["vendor_id", "country", "category", "status"]],
        on="vendor_id",
        how="left",
        validate="many_to_one",
    )
    if merged["status"].isna().any():
        raise ValueError("Invoice references a vendor_id missing from vendor_master")
    return merged
