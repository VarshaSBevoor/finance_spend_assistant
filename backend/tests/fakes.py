from app.llm import LLM
from app.plan import Plan
from app.schemas import Evidence


class FakeLLM(LLM):
    """Returns fixed plans in order and one fixed answer. Used in tests only."""

    backend = "fake"
    model = "fake"
    stub = True

    def __init__(self, plans: list[dict], answer: str = "") -> None:
        self.plans = [Plan.model_validate(plan) for plan in plans]
        self.answer = answer
        self.feedbacks: list[str | None] = []  # what each plan() call was told about an earlier rejection
        self.compose_calls = 0

    def plan(self, question: str, feedback: str | None = None) -> Plan:
        self.feedbacks.append(feedback)
        return self.plans.pop(0)

    def compose(self, question: str, evidence: Evidence) -> str:
        self.compose_calls += 1
        return self.answer
