from pathlib import Path

import pandas as pd

# Built from this file's location, so it works from any working directory.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_invoices(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Invoices joined with vendor country, category and status.

    Blank po_number and approved_by cells become NaN. They are real values
    (missing PO, missing approver), so nothing fills them in.
    """
    invoices = pd.read_csv(
        data_dir / "invoices_2025_clean.csv",
        parse_dates=["invoice_date"],
        # Only an empty cell counts as missing. Text like "NA" stays as text.
        keep_default_na=False,
        na_values=[""],
    )
    vendors = pd.read_csv(data_dir / "vendor_master.csv")

    # Left join keeps every invoice. vendor_name is already on the invoices,
    # so only the vendor columns we lack are added.
    merged = invoices.merge(
        vendors[["vendor_id", "country", "category", "status"]],
        on="vendor_id",
        how="left",
        # Fails if a vendor_id appears twice in the master, which would copy
        # invoice rows and double-count spend.
        validate="many_to_one",
    )
    # An unmatched vendor leaves status empty. Stop at startup instead of
    # letting a vendor with no status into the answers.
    if merged["status"].isna().any():
        raise ValueError("Invoice references a vendor_id missing from vendor_master")
    return merged
