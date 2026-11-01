import pandas as pd

from app.execute import run_data_query
from app.fallback import build_fallback_answer
from app.llm import LLM, PROMPT_VERSION, PlanError
from app.plan import Plan, Route
from app.schemas import AskResponse, Check, Evidence, Meta, PolicyEvidence
from app.validate import PlanRejected, validate_plan
from app.verify import all_passed, verify_answer


def answer_question(question: str, llm: LLM, invoices: pd.DataFrame, policy: dict[str, str]) -> AskResponse:
    """Plan, validate, execute, compose, verify, respond."""
    # 1 and 2. Plan, then validate. A rejected plan gets one retry with the reasons.
    try:
        plan, notes = plan_and_validate(question, llm, invoices, set(policy))
    except (PlanError, PlanRejected) as error:
        failed = Check(name="plan_validated", passed=False, detail=str(error))
        return decline(
            "I could not turn that question into a valid query, so I did not guess. Try rephrasing it.",
            llm,
            checks=[failed],
        )

    plan_checks = [Check(name="plan_validated", passed=True, detail="Only known columns, operators, values and policy sections.")]
    plan_checks += [Check(name="plan_repaired", passed=True, detail=note) for note in notes]

    if plan.route == "out_of_scope":
        reason = f"I can only answer questions about the 2025 invoices and the procurement policy. {plan.reason}"
        return decline(reason, llm, checks=plan_checks)

    # 3. Execute. pandas runs the query and the policy text is copied by section id.
    data = run_data_query(invoices, plan.data_query) if plan.data_query is not None else None
    sections = [PolicyEvidence(section_id=section_id, text=policy[section_id]) for section_id in plan.policy_sections]
    evidence = Evidence(policy=sections, data=data)

    if data is not None and data.matched_invoice_count == 0 and not sections:
        reason = f"No invoices match that question, so there is nothing to report. {data.how_computed}"
        return decline(reason, llm, route=plan.route, evidence=evidence, checks=plan_checks)

    # 4 and 5. Compose, then verify. If verification fails, use the answer built from the evidence.
    lead = llm.compose(question, evidence)
    verification = verify_answer(lead, question, evidence)

    if all_passed(verification):
        # For a long result the lead only summarises. The rows are in the evidence, built by
        # code, and the UI shows them as a table under the answer.
        answer = lead
        fallback_used = False
    else:
        answer = build_fallback_answer(evidence)
        fallback_used = True

    # 6. Respond.
    return AskResponse(
        answer=answer,
        declined=False,
        route=plan.route,
        evidence=evidence,
        checks=plan_checks + verification,
        meta=make_meta(llm, fallback_used),
    )


def plan_and_validate(question: str, llm: LLM, invoices: pd.DataFrame, policy_ids: set[str]) -> tuple[Plan, list[str]]:
    plan = llm.plan(question)
    try:
        return validate_plan(plan, invoices, policy_ids)
    except PlanRejected as rejected:
        plan = llm.plan(question, feedback=str(rejected))
        return validate_plan(plan, invoices, policy_ids)  # a second rejection is raised to the caller


def make_meta(llm: LLM, fallback_used: bool) -> Meta:
    return Meta(
        backend=llm.backend,
        model=llm.model,
        prompt_version=PROMPT_VERSION,
        stub=llm.stub,
        fallback_used=fallback_used,
    )


def decline(
    reason: str,
    llm: LLM,
    route: Route = "out_of_scope",
    evidence: Evidence | None = None,
    checks: list[Check] | None = None,
) -> AskResponse:
    return AskResponse(
        answer=reason,
        declined=True,
        route=route,
        evidence=evidence or Evidence(policy=[], data=None),
        checks=checks or [],
        meta=make_meta(llm, fallback_used=False),
    )
