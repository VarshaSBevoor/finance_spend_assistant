from datetime import datetime

import pandas as pd

from app.plan import Filter, Plan

# Rules, in one place:
# 1. Every column in a filter, group_by or show_columns must exist.
# 2. The operator must fit the column (gt/lt only on amount and date, is_null only on PO and approver).
# 3. The value must fit the operator and the column (a number for amount, YYYY-MM-DD for date,
#    a known value for currency, status, country, category and approved_by).
# 4. Every policy section id must exist.
# 5. Repair: a "sum" always groups by currency, so amounts in different currencies are never added.
COLUMNS = [
    "invoice_number", "invoice_date", "vendor_id", "vendor_name", "description", "amount",
    "currency", "cost_center", "po_number", "approved_by", "country", "category", "status",
]
NUMBER_COLUMNS = ["amount"]
DATE_COLUMNS = ["invoice_date"]
NULLABLE_COLUMNS = ["po_number", "approved_by"]
# Columns with a small set of values. The allowed values are read from the data.
# approved_by is here so that an invented name such as "requester" is rejected, not matched to nothing.
CLOSED_COLUMNS = ["currency", "status", "country", "category", "approved_by"]

MATCH_OPS = ["eq", "ne", "in"]
COMPARE_OPS = ["gt", "gte", "lt", "lte"]
NULL_OPS = ["is_null", "not_null"]


class PlanRejected(Exception):
    """The plan names something that does not exist or does not make sense."""


def validate_plan(plan: Plan, invoices: pd.DataFrame, policy_ids: set[str]) -> tuple[Plan, list[str]]:
    """Return the plan (repaired if needed) and notes about repairs. Raise PlanRejected if it is bad."""
    problems: list[str] = []
    query = plan.data_query

    if query is not None:
        for one_filter in query.filters:
            problems += check_filter(one_filter, invoices)
        for column in query.group_by:
            if column not in COLUMNS:
                problems.append(f"group_by column '{column}' does not exist. Use one of: {', '.join(COLUMNS)}.")
        for column in query.show_columns:
            if column not in COLUMNS:
                problems.append(f"show_columns column '{column}' does not exist. Use one of: {', '.join(COLUMNS)}.")

    for section_id in plan.policy_sections:
        if section_id not in policy_ids:
            problems.append(f"policy section '{section_id}' does not exist. Use one of: {', '.join(sorted(policy_ids))}.")

    if problems:
        raise PlanRejected("\n".join(problems))

    notes: list[str] = []
    if query is not None and query.aggregate == "sum" and "currency" not in query.group_by:
        query = query.model_copy(update={"group_by": query.group_by + ["currency"]})
        plan = plan.model_copy(update={"data_query": query})
        notes.append("Added currency to group_by: amounts in different currencies are never added together.")
    return plan, notes


def check_filter(one_filter: Filter, invoices: pd.DataFrame) -> list[str]:
    column = one_filter.column
    if column not in COLUMNS:
        return [f"filter column '{column}' does not exist. Use one of: {', '.join(COLUMNS)}."]

    allowed_ops = list(MATCH_OPS)
    if column in NUMBER_COLUMNS or column in DATE_COLUMNS:
        allowed_ops += COMPARE_OPS
    if column in NULLABLE_COLUMNS:
        allowed_ops += NULL_OPS
    if one_filter.op not in allowed_ops:
        return [f"operator '{one_filter.op}' cannot be used on column '{column}'. Allowed: {', '.join(allowed_ops)}."]

    value = one_filter.value
    if one_filter.op in NULL_OPS:
        return [f"operator '{one_filter.op}' takes no value."] if value is not None else []
    if value is None:
        return [f"operator '{one_filter.op}' on '{column}' needs a value."]
    if one_filter.op == "in" and not isinstance(value, list):
        return [f"operator 'in' on '{column}' needs a list of values."]
    if one_filter.op != "in" and isinstance(value, list):
        return [f"operator '{one_filter.op}' on '{column}' needs one value, not a list."]

    values = value if isinstance(value, list) else [value]
    problems = []
    for item in values:
        if column in NUMBER_COLUMNS:
            if not isinstance(item, (int, float)):
                problems.append(f"'{column}' needs a number, got '{item}'.")
        elif column in DATE_COLUMNS:
            if not is_iso_date(item):
                problems.append(f"'{column}' needs a date like 2025-03-09, got '{item}'.")
        elif column in CLOSED_COLUMNS:
            # A missing value is not a name to offer, and letter case is ignored like in execute.py.
            allowed_values = sorted(invoices[column].dropna().unique())
            if str(item).strip().casefold() not in [allowed.casefold() for allowed in allowed_values]:
                problems.append(f"'{item}' is not a value of '{column}'. Use one of: {', '.join(allowed_values)}.")
    return problems


def is_iso_date(value) -> bool:
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return True
    except ValueError:
        return False
