from app.data import load_invoices
from app.pipeline import answer_question
from app.policy import load_policy
from tests.fakes import FakeLLM

INVOICES = load_invoices()
POLICY = load_policy()

SPAIN_PLAN = {
    "route": "data",
    "data_query": {
        "filters": [{"column": "country", "op": "eq", "value": "Spain"}],
        "group_by": ["currency"],
        "aggregate": "sum",
    },
    "policy_sections": [],
    "reason": "Spend by vendor country.",
}
BAD_COLUMN_PLAN = {
    "route": "data",
    "data_query": {"filters": [{"column": "vendor", "op": "eq", "value": "Alpha"}], "group_by": [], "aggregate": "count"},
    "policy_sections": [],
    "reason": "x",
}
TOP_5_PLAN = {
    "route": "data",
    "data_query": {"filters": [], "group_by": ["vendor_name", "currency"], "aggregate": "sum", "sort": "desc", "limit": 5},
    "policy_sections": [],
    "reason": "x",
}
OUT_OF_SCOPE_PLAN = {"route": "out_of_scope", "data_query": None, "policy_sections": [], "reason": "The data has no requester field."}
QUESTION = "What is our total spend with vendors based in Spain?"
SPAIN_ANSWER = "Across 49 invoices, vendors in Spain were paid EUR 1,576,971.22, GBP 646,618.51 and USD 343,748.06 [data]."


def ask(llm: FakeLLM, question: str = QUESTION):
    return answer_question(question, llm, INVOICES, POLICY)


def test_a_verified_answer_is_returned_with_its_evidence_and_meta():
    response = ask(FakeLLM([SPAIN_PLAN], SPAIN_ANSWER))

    assert response.answer == SPAIN_ANSWER
    assert not response.declined and not response.meta.fallback_used
    assert response.route == "data"
    assert response.evidence.data.matched_invoice_count == 49
    assert response.meta.stub and response.meta.backend == "fake"
    assert all(check.passed for check in response.checks)


def test_an_answer_with_an_invented_number_is_replaced_by_the_fallback():
    response = ask(FakeLLM([SPAIN_PLAN], "Vendors in Spain were paid EUR 9,999.00 [data]."))

    assert response.meta.fallback_used
    assert "1,576,971.22" in response.answer  # built from the evidence
    assert not next(check for check in response.checks if check.name == "numbers_in_evidence").passed


def test_a_rejected_plan_is_retried_once_with_the_reasons_and_then_answered():
    llm = FakeLLM([BAD_COLUMN_PLAN, SPAIN_PLAN], SPAIN_ANSWER)

    response = ask(llm)

    assert llm.feedbacks[0] is None
    assert "'vendor' does not exist" in llm.feedbacks[1]
    assert not response.declined


def test_a_plan_rejected_twice_is_declined_and_never_composed():
    llm = FakeLLM([BAD_COLUMN_PLAN, BAD_COLUMN_PLAN], "should not be used")

    response = ask(llm)

    assert response.declined and llm.compose_calls == 0
    assert not response.checks[0].passed


def test_an_out_of_scope_question_is_declined_with_the_reason():
    llm = FakeLLM([OUT_OF_SCOPE_PLAN], "should not be used")

    response = ask(llm, "Who requested the purchase for INV-20010?")

    assert response.declined and llm.compose_calls == 0
    assert "no requester field" in response.answer
    assert response.evidence.data is None and response.evidence.policy == []


def test_a_long_result_gets_the_models_summary_and_every_row_listed_by_code():
    lead = "Across 140 invoices, the top 5 vendors are ranked per currency, because amounts in different currencies are never added together [data]."

    response = ask(FakeLLM([TOP_5_PLAN], lead), "What are our top 5 vendors by total spend in 2025?")

    assert response.answer.startswith(lead)
    assert response.answer.count("- vendor_name:") == 15  # 5 for each of EUR, GBP and USD
    assert "Currency GBP:" in response.answer
    assert not response.meta.fallback_used


def test_a_question_with_no_matching_invoices_is_declined_and_never_composed():
    no_match_plan = {
        "route": "data",
        "data_query": {"filters": [{"column": "amount", "op": "gt", "value": 99999999.0}], "group_by": [], "aggregate": "rows"},
        "policy_sections": [],
        "reason": "x",
    }
    llm = FakeLLM([no_match_plan], "should not be used")

    response = ask(llm, "Show me invoices above 99999999")

    assert response.declined and llm.compose_calls == 0
    assert response.evidence.data.matched_invoice_count == 0  # the evidence still shows what was tried
    assert "nothing to report" in response.answer
