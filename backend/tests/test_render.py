from app.llm import COMPOSE_PROMPT, PROMPTS_DIR
from app.render import LIST_ROW_THRESHOLD, render_rows


def test_rows_are_listed_in_order_under_a_heading_per_currency_and_cut_in_words():
    rows = [
        {"vendor_name": "A", "currency": "EUR", "total_amount": 300.0, "po_number": None},
        {"vendor_name": "B", "currency": "EUR", "total_amount": 200.0, "po_number": "PO-1"},
        {"vendor_name": "C", "currency": "GBP", "total_amount": 1500.5, "po_number": None},
    ]

    lines = render_rows(rows, max_rows=2).splitlines()

    assert lines == [
        "Currency EUR:",
        "- vendor_name: A, currency: EUR, total_amount: 300.00, po_number: missing",
        "- vendor_name: B, currency: EUR, total_amount: 200.00, po_number: PO-1",
        "More rows are in the evidence table.",
    ]
    assert "- vendor_name: C, currency: GBP, total_amount: 1,500.50, po_number: missing" in render_rows(rows)


def test_the_compose_prompt_states_the_same_row_threshold_as_the_code():
    prompt = (PROMPTS_DIR / f"{COMPOSE_PROMPT}.txt").read_text()

    assert f"more than {LIST_ROW_THRESHOLD} rows" in prompt
