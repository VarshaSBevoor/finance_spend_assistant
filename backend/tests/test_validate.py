import pandas as pd
import pytest
from pydantic import ValidationError

from app.plan import Plan
from app.validate import PlanRejected, validate_plan

INVOICES = pd.DataFrame(
    {
        "currency": ["EUR", "GBP"],
        "status": ["ACTIVE", "ON_HOLD"],
        "country": ["Spain", "UK"],
        "category": ["Facilities", "Travel"],
        "approved_by": ["r.okafor", None],
    }
)
POLICY_IDS = {"2.2", "3"}


def make_plan(filters=None, group_by=None, aggregate="sum", sections=None, show_columns=None) -> Plan:
    route = "both" if sections else "data"
    return Plan.model_validate(
        {
            "route": route,
            "data_query": {
                "filters": filters or [],
                "group_by": group_by or [],
                "aggregate": aggregate,
                "show_columns": show_columns or [],
            },
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


def test_an_unknown_column_in_show_columns_is_rejected_with_the_allowed_names():
    plan = make_plan(aggregate="rows", show_columns=["po_num"])

    with pytest.raises(PlanRejected) as error:
        validate_plan(plan, INVOICES, POLICY_IDS)

    assert "show_columns column 'po_num' does not exist" in str(error.value)
    assert "po_number" in str(error.value)  # the allowed names are listed, so the retry can fix it


def test_show_columns_is_only_allowed_when_listing_invoices():
    with pytest.raises(ValidationError) as error:
        make_plan(aggregate="sum", group_by=["vendor_name"], show_columns=["po_number"])

    assert "show_columns" in str(error.value)


def test_an_approver_that_does_not_exist_is_rejected_and_the_real_names_are_listed():
    plan = make_plan(filters=[{"column": "approved_by", "op": "eq", "value": "requester"}], aggregate="rows")

    with pytest.raises(PlanRejected) as error:
        validate_plan(plan, INVOICES, POLICY_IDS)

    assert "'requester' is not a value of 'approved_by'" in str(error.value)
    assert "r.okafor" in str(error.value)  # the missing value is not offered as a name


def test_a_known_approver_is_accepted_in_any_letter_case():
    plan = make_plan(filters=[{"column": "approved_by", "op": "eq", "value": "R.OKAFOR"}], aggregate="rows")

    validate_plan(plan, INVOICES, POLICY_IDS)  # raises PlanRejected if the rule is too strict
