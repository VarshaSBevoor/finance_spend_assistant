from app.render import LIST_ROW_THRESHOLD, format_row
from app.schemas import DataResult, Evidence, PolicyEvidence


def build_fallback_answer(evidence: Evidence) -> str:
    """An answer made only from the evidence, with no model. Stiff, but always faithful."""
    parts = []
    if evidence.data is not None:
        parts.append(describe_data(evidence.data))
    for section in evidence.policy:
        parts.append(describe_policy(section))
    return "\n\n".join(parts)


def describe_data(data: DataResult) -> str:
    if not data.rows:
        return f"No invoices matched. {data.how_computed} [data]"

    if len(data.rows) > LIST_ROW_THRESHOLD:
        # A long result is shown as a table beside the answer, not retyped here.
        return (
            f"{data.matched_invoice_count} invoices matched. "
            f"The {len(data.rows)} result rows are in the evidence table [data]. {data.how_computed}"
        )

    rows_text = "; ".join(format_row(row) for row in data.rows)
    return f"{data.matched_invoice_count} invoices matched. Results: {rows_text} [data]. {data.how_computed}"


def describe_policy(section: PolicyEvidence) -> str:
    return f"{section.text} [policy {section.section_id}]"
