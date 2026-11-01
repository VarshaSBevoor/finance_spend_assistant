from app.schemas import DataResult, Evidence, PolicyEvidence
from app.verify import all_passed, verify_answer

EVIDENCE = Evidence(
    policy=[PolicyEvidence(section_id="3", text="| 50,000.01 – 250,000 | Finance Director |")],
    data=DataResult(
        rows=[{"currency": "EUR", "total_amount": 150.0, "invoice_count": 2}],
        matched_invoice_count=2,
        how_computed="Filters: country = Spain. Summed the amount for each currency.",
    ),
)
QUESTION = "What is our total spend with Spain, and who approves EUR 60,000?"
FAITHFUL = "Spanish vendors total EUR 150.00 across 2 invoices [data]. EUR 60,000 needs the Finance Director [policy 3]."


def check_named(checks, name):
    return next(check for check in checks if check.name == name)


def test_an_invented_number_is_caught():
    answer = "Spanish vendors total EUR 1,500.00 across 2 invoices [data]. The Finance Director approves [policy 3]."

    checks = verify_answer(answer, QUESTION, EVIDENCE)

    numbers_check = check_named(checks, "numbers_in_evidence")
    assert not numbers_check.passed
    assert "1500" in numbers_check.detail
    assert not all_passed(checks)


def test_a_faithful_answer_passes_including_numbers_from_the_question():
    checks = verify_answer(FAITHFUL, QUESTION, EVIDENCE)

    assert all_passed(checks)


def test_a_number_from_data_cannot_be_attributed_to_a_policy_section():
    # 150 is real, but it comes from the data, and this sentence cites the policy.
    answer = "The Finance Director approves EUR 150.00 [policy 3]. Spain has 2 invoices [data]."

    checks = verify_answer(answer, QUESTION, EVIDENCE)

    numbers_check = check_named(checks, "numbers_in_evidence")
    assert not numbers_check.passed
    assert "150" in numbers_check.detail


def test_citing_a_missing_policy_section_or_missing_data_fails():
    evidence_without_data = Evidence(policy=EVIDENCE.policy, data=None)
    answer = "Per [policy 9.9] and the numbers in [data], the Finance Director approves."

    checks = verify_answer(answer, QUESTION, evidence_without_data)

    citations_check = check_named(checks, "citations_exist")
    assert not citations_check.passed
    assert "9.9" in citations_check.detail
    assert "no data evidence" in citations_check.detail


def test_an_answer_must_cite_each_kind_of_evidence_it_was_given():
    no_citation = "The Finance Director approves it."
    only_data = "Spanish vendors total EUR 150.00 [data]."

    assert not check_named(verify_answer(no_citation, QUESTION, EVIDENCE), "answer_is_cited").passed
    only_data_check = check_named(verify_answer(only_data, QUESTION, EVIDENCE), "answer_is_cited")
    assert not only_data_check.passed
    assert "[policy" in only_data_check.detail


def test_a_per_currency_top_n_must_say_the_ranking_is_per_currency():
    ranked = Evidence(
        policy=[],
        data=DataResult(
            rows=[{"currency": "EUR", "total_amount": 150.0}, {"currency": "GBP", "total_amount": 70.0}],
            matched_invoice_count=3,
            how_computed="Limit of 1 applied per currency.",
            limit_per_currency=True,
        ),
    )
    one_list = "The top vendors are EUR 150.00 and GBP 70.00 [data]."
    stated = "The top vendor per currency is EUR 150.00 and GBP 70.00 [data]."

    assert not check_named(verify_answer(one_list, "Top vendor?", ranked), "per_currency_stated").passed
    assert check_named(verify_answer(stated, "Top vendor?", ranked), "per_currency_stated").passed
    # Evidence without a per-currency limit is not affected.
    assert check_named(verify_answer(FAITHFUL, QUESTION, EVIDENCE), "per_currency_stated").passed
