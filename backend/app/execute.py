import pandas as pd

from app.plan import DataQuery, Filter
from app.schemas import DataResult

OPERATOR_TEXT = {
    "eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
    "in": "in", "is_null": "is missing", "not_null": "is present",
}

# A list of invoices shows these columns, plus any column the question asked to see or filtered on.
# Thirteen columns per row is too much to read at a glance.
CORE_ROW_COLUMNS = ["invoice_number", "invoice_date", "vendor_name", "amount", "currency"]


def columns_for_rows(query: DataQuery) -> list[str]:
    columns = list(CORE_ROW_COLUMNS)
    for column in query.show_columns:
        if column not in columns:
            columns.append(column)
    for one_filter in query.filters:
        if one_filter.column not in columns:
            columns.append(one_filter.column)
    return columns


def comparable_text(column: pd.Series) -> pd.Series:
    """Trim and lowercase a text column, so that "mgmt" finds "Mgmt". Other columns are returned as they are."""
    if pd.api.types.is_string_dtype(column):
        return column.str.strip().str.casefold()
    return column


def comparable_value(value):
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, list):
        return [comparable_value(item) for item in value]
    return value


def apply_filters(invoices: pd.DataFrame, filters: list[Filter]) -> pd.DataFrame:
    """Keep only the invoices that match every filter (AND)."""
    result = invoices

    for one_filter in filters:
        column = result[one_filter.column]
        value = one_filter.value
        op = one_filter.op

        # People type names in any case. Missing values stay missing, so "not equal to X" still keeps them.
        if op in ("eq", "ne", "in"):
            column = comparable_text(column)
            value = comparable_value(value)

        # Each branch builds a True/False value per row. True rows are kept.
        if op == "eq":
            keep = column == value
        elif op == "ne":
            keep = column != value
        elif op == "gt":
            keep = column > value
        elif op == "gte":
            keep = column >= value
        elif op == "lt":
            keep = column < value
        elif op == "lte":
            keep = column <= value
        elif op == "in":
            keep = column.isin(value)
        elif op == "is_null":
            keep = column.isna()
        elif op == "not_null":
            keep = column.notna()
        else:
            raise ValueError(f"Unknown operator: {op}")

        result = result[keep]

    return result


def aggregate(filtered: pd.DataFrame, query: DataQuery) -> pd.DataFrame:
    """One row per group with the numbers. "rows" returns the invoices as they are."""
    if query.aggregate == "rows" or filtered.empty:
        return filtered

    if query.group_by:
        # dropna=False keeps invoices whose group value is missing (for example
        # no approver) as their own group. Missing is a real value here.
        grouped = filtered.groupby(query.group_by, dropna=False)
        summary = grouped.agg(
            total_amount=("amount", "sum"),
            invoice_count=("amount", "size"),
        ).reset_index()
    else:
        summary = pd.DataFrame(
            [{"total_amount": filtered["amount"].sum(), "invoice_count": len(filtered)}]
        )

    summary["total_amount"] = summary["total_amount"].round(2)
    if query.aggregate == "count":
        summary = summary.drop(columns="total_amount")
    return summary


def order_and_limit(table: pd.DataFrame, query: DataQuery) -> pd.DataFrame:
    """Order by currency, then by value in the requested direction. Limit per currency."""
    if table.empty:
        return table

    # The column that "sort" refers to depends on what we aggregated.
    value_column = {"sum": "total_amount", "count": "invoice_count", "rows": "amount"}[query.aggregate]
    has_currency = "currency" in table.columns

    sort_columns = []
    ascending = []
    if has_currency:
        # Currencies cannot be ranked against each other, so each gets its own block.
        sort_columns.append("currency")
        ascending.append(True)
    if query.sort is not None:
        sort_columns.append(value_column)
        ascending.append(query.sort == "asc")

    if sort_columns:
        table = table.sort_values(sort_columns, ascending=ascending, kind="stable")

    if query.limit is not None:
        if has_currency:
            table = table.groupby("currency").head(query.limit)
        else:
            table = table.head(query.limit)
    return table


def to_records(table: pd.DataFrame) -> list[dict]:
    """Rows as plain dicts that JSON can carry: dates as text, missing as None."""
    table = table.copy()
    for column in table.columns:
        if pd.api.types.is_datetime64_any_dtype(table[column]):
            table[column] = table[column].dt.strftime("%Y-%m-%d")
    # where() replaces every missing value (NaN, NaT) with None.
    table = table.astype(object).where(table.notna(), None)
    return table.to_dict("records")


def limit_is_per_currency(query: DataQuery) -> bool:
    """A limit is applied per currency whenever the result has a currency column."""
    return query.limit is not None and (query.aggregate == "rows" or "currency" in query.group_by)


def describe_filter(one_filter: Filter) -> str:
    text = OPERATOR_TEXT[one_filter.op]
    if one_filter.op in ("is_null", "not_null"):
        return f"{one_filter.column} {text}"
    return f"{one_filter.column} {text} {one_filter.value}"


def describe_query(query: DataQuery) -> str:
    """Plain-language account of what was done. It is shown to the analyst as evidence."""
    if query.filters:
        parts = ["Filters: " + "; ".join(describe_filter(f) for f in query.filters) + "."]
    else:
        parts = ["No filters, all invoices."]

    groups = ", ".join(query.group_by)
    for_each = f" for each {groups}" if groups else ""
    if query.aggregate == "rows":
        parts.append(f"Listed the matching invoices (columns: {', '.join(columns_for_rows(query))}).")
    elif query.aggregate == "count":
        parts.append(f"Counted invoices{for_each}.")
    else:
        parts.append(f"Summed the amount{for_each}. Amounts in different currencies are never added together.")

    if query.sort is not None:
        value_name = {"sum": "total amount", "count": "invoice count", "rows": "amount"}[query.aggregate]
        direction = "largest" if query.sort == "desc" else "smallest"
        parts.append(f"Ordered by {value_name}, {direction} first.")

    if query.limit is not None:
        if limit_is_per_currency(query):
            parts.append(f"Limit of {query.limit} applied per currency, because currencies cannot be ranked against each other.")
        else:
            parts.append(f"Limit of {query.limit} applied.")
    return " ".join(parts)


def run_data_query(invoices: pd.DataFrame, query: DataQuery) -> DataResult:
    filtered = apply_filters(invoices, query.filters)
    table = order_and_limit(aggregate(filtered, query), query)
    if query.aggregate == "rows" and not table.empty:
        table = table[columns_for_rows(query)]  # after sorting, which may need other columns
    return DataResult(
        rows=to_records(table),
        matched_invoice_count=len(filtered),
        how_computed=describe_query(query),
        limit_per_currency=limit_is_per_currency(query),
    )
