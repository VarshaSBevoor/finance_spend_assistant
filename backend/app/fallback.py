from app.render import format_row
from app.schemas import DataResult, Evidence, PolicyEvidence

# Long results are cut. The words, not a number, say so, because a number we
# invented would fail the number check in verify.py.
MAX_ROWS_LISTED = 10


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

    rows_text = "; ".join(format_row(row) for row in data.rows[:MAX_ROWS_LISTED])
    if len(data.rows) > MAX_ROWS_LISTED:
        rows_text += "; more rows are in the evidence table"
    return f"{data.matched_invoice_count} invoices matched. Results: {rows_text} [data]. {data.how_computed}"


def describe_policy(section: PolicyEvidence) -> str:
    return f"{section.text} [policy {section.section_id}]"
