import pandas as pd
import pytest

from app.plan import Plan
from app.validate import PlanRejected, validate_plan

INVOICES = pd.DataFrame(
    {
        "currency": ["EUR", "GBP"],
        "status": ["ACTIVE", "ON_HOLD"],
        "country": ["Spain", "UK"],
        "category": ["Facilities", "Travel"],
    }
)
POLICY_IDS = {"2.2", "3"}


def make_plan(filters=None, group_by=None, aggregate="sum", sections=None) -> Plan:
    route = "both" if sections else "data"
    return Plan.model_validate(
        {
            "route": route,
            "data_query": {"filters": filters or [], "group_by": group_by or [], "aggregate": aggregate},
            "policy_sections": sections or [],
            "reason": "test",
        }
    )


def test_bad_column_value_operator_and_section_are_all_reported():
    plan = make_plan(
        filters=[
            {"column": "vendor", "op": "eq", "value": "Acme"},          # no such column
            {"column": "status", "op": "eq", "value": "PAUSED"},        # not a status value
            {"column": "currency", "op": "gt", "value": "EUR"},         # gt does not fit currency
        ],
        sections=["99"],                                                # no such section
    )

    with pytest.raises(PlanRejected) as error:
        validate_plan(plan, INVOICES, POLICY_IDS)

    message = str(error.value)
    assert "'vendor' does not exist" in message
    assert "'PAUSED' is not a value of 'status'" in message
    assert "operator 'gt' cannot be used on column 'currency'" in message
    assert "policy section '99' does not exist" in message


def test_sum_without_currency_is_repaired_and_a_note_is_returned():
    plan = make_plan(group_by=["vendor_name"], aggregate="sum")

    repaired, notes = validate_plan(plan, INVOICES, POLICY_IDS)

    assert repaired.data_query.group_by == ["vendor_name", "currency"]
    assert len(notes) == 1
    assert plan.data_query.group_by == ["vendor_name"]  # the original plan is unchanged
