from pathlib import Path

import httpx
from pydantic import ValidationError

from app.plan import Plan
from app.render import render_rows
from app.schemas import Evidence
from app.settings import DEFAULT_HOST, DEFAULT_MODEL

# Bump the matching name whenever a prompt file changes. PROMPT_VERSION goes in the response meta.
PLAN_PROMPT = "plan_v3"
COMPOSE_PROMPT = "compose_v2"
PROMPT_VERSION = f"{PLAN_PROMPT}+{COMPOSE_PROMPT}"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

# The model sees at most this many rows, so a long result cannot fill its context.
MAX_ROWS_FOR_MODEL = 20


class LLMError(Exception):
    """Ollama could not be reached, timed out, or returned an error."""


class PlanError(Exception):
    """The model did not return a valid plan, even after one retry."""


class LLM:
    """What the pipeline needs from a model. Tests use a fake with the same methods."""

    # Shown in the response meta so a reader knows what produced the answer.
    backend = "none"
    model = "none"
    stub = False

    def plan(self, question: str, feedback: str | None = None) -> Plan:
        raise NotImplementedError

    def compose(self, question: str, evidence: Evidence) -> str:
        raise NotImplementedError


class OllamaLLM(LLM):
    backend = "ollama"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host
        self.timeout = timeout
        self.plan_prompt = (PROMPTS_DIR / f"{PLAN_PROMPT}.txt").read_text()
        self.compose_prompt = (PROMPTS_DIR / f"{COMPOSE_PROMPT}.txt").read_text()

    def plan(self, question: str, feedback: str | None = None) -> Plan:
        user_message = question
        if feedback:
            # The pipeline passes this when the validator rejected an earlier plan.
            user_message += f"\n\nAn earlier plan for this question was rejected:\n{feedback}\nFix these problems."

        messages = [
            {"role": "system", "content": self.plan_prompt},
            {"role": "user", "content": user_message},
        ]
        last_error = None

        # Two attempts: the first, then one retry that shows the model what was wrong.
        for attempt in range(2):
            reply = self._chat(messages, Plan.model_json_schema())
            try:
                return Plan.model_validate_json(reply)
            except ValidationError as error:
                last_error = error
                messages.append({"role": "assistant", "content": reply})
                messages.append(
                    {
                        "role": "user",
                        "content": f"That plan was invalid:\n{error}\nReturn a corrected plan as JSON only.",
                    }
                )

        raise PlanError("The model did not return a valid plan after one retry.") from last_error

    def compose(self, question: str, evidence: Evidence) -> str:
        messages = [
            {"role": "system", "content": self.compose_prompt},
            {"role": "user", "content": f"QUESTION: {question}\nEVIDENCE\n{evidence_as_text(evidence)}\nANSWER:"},
        ]
        return self._chat(messages, schema=None).strip()

    def _chat(self, messages: list[dict], schema: dict | None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        if schema is not None:
            payload["format"] = schema  # Ollama restricts the reply to this JSON shape
        try:
            response = httpx.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.ConnectError as error:
            raise LLMError("Cannot reach Ollama. Is it running?") from error
        except httpx.TimeoutException as error:
            raise LLMError("Ollama took too long to respond.") from error
        except httpx.HTTPStatusError as error:
            raise LLMError(f"Ollama returned an error (status {error.response.status_code}).") from error

        return response.json()["message"]["content"]


def evidence_as_text(evidence: Evidence) -> str:
    """The evidence in the layout the compose prompt shows in its examples."""
    blocks = []
    if evidence.data is not None:
        data = evidence.data
        lines = [
            "[data]",
            f"How it was computed: {data.how_computed}",
            f"Invoices matched: {data.matched_invoice_count}",
            "Rows:" if data.rows else "Rows: none",
        ]
        if data.rows:
            lines.append(render_rows(data.rows, MAX_ROWS_FOR_MODEL))
        blocks.append("\n".join(lines))

    for section in evidence.policy:
        blocks.append(f"[policy {section.section_id}]\n{section.text}")
    return "\n".join(blocks)
