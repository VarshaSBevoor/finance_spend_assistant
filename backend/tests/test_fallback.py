from app.data import load_invoices
from app.execute import run_data_query
from app.fallback import build_fallback_answer
from app.plan import DataQuery
from app.policy import load_policy
from app.render import LIST_ROW_THRESHOLD
from app.schemas import DataResult, Evidence, PolicyEvidence
from app.verify import all_passed, verify_answer


def test_fallback_for_small_evidence_passes_verification_and_shows_missing_values():
    evidence = Evidence(
        policy=[PolicyEvidence(section_id="3.1", text="3.1 Invoices lacking an approver record must be held.")],
        data=DataResult(
            rows=[{"approved_by": None, "invoice_count": 25}],
            matched_invoice_count=25,
            how_computed="No filters, all invoices. Counted invoices for each approved_by.",
        ),
    )
    question = "How many invoices have no approver?"

    answer = build_fallback_answer(evidence)

    assert "approved_by: missing" in answer
    assert "[data]" in answer and "[policy 3.1]" in answer
    assert all_passed(verify_answer(answer, question, evidence))


def test_fallback_for_a_real_top_5_question_passes_verification_and_points_to_the_table():
    query = DataQuery.model_validate(
        {"filters": [], "group_by": ["vendor_name", "currency"], "aggregate": "sum", "sort": "desc", "limit": 5}
    )
    result = run_data_query(load_invoices(), query)
    policy = load_policy()
    evidence = Evidence(policy=[PolicyEvidence(section_id="3", text=policy["3"])], data=result)
    question = "What are our top 5 vendors by total spend in 2025?"

    answer = build_fallback_answer(evidence)

    assert len(result.rows) > LIST_ROW_THRESHOLD  # 15 rows: 5 per currency
    assert "result rows are in the evidence table" in answer
    assert "vendor_name:" not in answer  # the rows are not retyped
    assert all_passed(verify_answer(answer, question, evidence))
