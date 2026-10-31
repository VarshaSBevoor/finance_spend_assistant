from pathlib import Path

import httpx
from pydantic import ValidationError

from app.plan import Plan

# Bump this whenever a prompt file changes. It is returned in the response meta.
PROMPT_VERSION = "plan_v3"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class LLMError(Exception):
    """Ollama could not be reached, timed out, or returned an error."""


class PlanError(Exception):
    """The model did not return a valid plan, even after one retry."""


class LLM:
    """What the pipeline needs from a model. Tests use a fake with the same methods."""

    def plan(self, question: str) -> Plan:
        raise NotImplementedError

    # The evidence type does not exist yet. It is defined when the pipeline is built.
    def compose(self, question: str, evidence: list) -> str:
        raise NotImplementedError


class OllamaLLM(LLM):
    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host
        self.timeout = timeout
        self.plan_prompt = (PROMPTS_DIR / f"{PROMPT_VERSION}.txt").read_text()

    def plan(self, question: str) -> Plan:
        messages = [
            {"role": "system", "content": self.plan_prompt},
            {"role": "user", "content": question},
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

    def _chat(self, messages: list[dict], schema: dict) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,  # Ollama restricts the reply to this JSON shape
            "options": {"temperature": 0, "num_ctx": 8192},
        }
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
