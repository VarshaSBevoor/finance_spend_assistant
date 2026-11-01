# Above this many rows, the model only summarises and code lists the rows.
# prompts/compose_v2.txt says the same number. A test keeps the two in step.
LIST_ROW_THRESHOLD = 3

# The answer lists at most this many rows. The evidence table in the UI has all of them.
MAX_ROWS_RENDERED = 30


def format_value(value) -> str:
    if value is None:
        return "missing"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def format_row(row: dict) -> str:
    return ", ".join(f"{name}: {format_value(value)}" for name, value in row.items())


def render_rows(rows: list[dict], max_rows: int = MAX_ROWS_RENDERED) -> str:
    """One line per row, in the order given. Rows with a currency go under a heading per currency."""
    shown = rows[:max_rows]
    lines = []

    if shown and all("currency" in row for row in shown):
        current_currency = None
        for row in shown:  # rows are already ordered by currency
            if row["currency"] != current_currency:
                current_currency = row["currency"]
                lines.append(f"Currency {current_currency}:")
            lines.append(f"- {format_row(row)}")
    else:
        lines = [f"- {format_row(row)}" for row in shown]

    if len(rows) > max_rows:
        lines.append("More rows are in the evidence table.")
    return "\n".join(lines)
