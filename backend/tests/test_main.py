import pytest
from fastapi.testclient import TestClient

from app.llm import OllamaLLM
from app.main import app
from tests.fakes import FakeLLM
from tests.test_pipeline import OUT_OF_SCOPE_PLAN, SPAIN_ANSWER, SPAIN_PLAN


def test_summary_returns_contract_shape_and_known_totals():
    # The `with` block matters: it runs the app's startup, which loads the data.
    with TestClient(app) as client:
        response = client.get("/summary")

    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "invoice_count",
        "spend_by_currency",
        "spend_by_currency_and_status",
        "missing_po_count",
        "missing_approver_count",
    }
    assert body["invoice_count"] == 140
    assert body["missing_po_count"] == 21
    assert body["missing_approver_count"] == 25

    totals = {row["currency"]: row["total"] for row in body["spend_by_currency"]}
    assert totals == {"EUR": 4493726.12, "GBP": 1182251.02, "USD": 1150445.53}


# The fake replaces the real model after startup, so these tests never call Ollama.
def post_ask(llm, question="What is our total spend with vendors based in Spain?"):
    with TestClient(app) as client:
        app.state.llm = llm
        return client.post("/ask", json={"question": question})


def test_ask_returns_the_contract_shape():
    response = post_ask(FakeLLM([SPAIN_PLAN], SPAIN_ANSWER))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "declined", "route", "evidence", "checks", "meta"}
    assert set(body["evidence"]) == {"policy", "data"}
    assert set(body["meta"]) == {"backend", "model", "prompt_version", "stub", "fallback_used"}
    assert body["answer"] == SPAIN_ANSWER and body["declined"] is False
    assert body["meta"]["stub"] is True  # a fake is labelled as a stub


def test_ask_declines_an_out_of_scope_question():
    response = post_ask(FakeLLM([OUT_OF_SCOPE_PLAN]), "Who requested the purchase for INV-20010?")

    assert response.status_code == 200
    assert response.json()["declined"] is True
    assert response.json()["evidence"] == {"policy": [], "data": None}


def test_ask_rejects_an_empty_question_and_reports_a_missing_model_as_503():
    assert post_ask(FakeLLM([]), question="").status_code == 422
    assert post_ask(FakeLLM([]), question="x" * 501).status_code == 422  # over the length limit

    unreachable = OllamaLLM(host="http://localhost:1")
    response = post_ask(unreachable)

    assert response.status_code == 503
    assert "Cannot reach Ollama" in response.json()["detail"]


def test_the_app_refuses_to_start_when_the_data_file_is_missing(monkeypatch):
    def missing_file(*args, **kwargs):
        raise FileNotFoundError("invoices file is missing")

    monkeypatch.setattr("app.main.load_invoices", missing_file)

    with pytest.raises(FileNotFoundError):
        with TestClient(app):
            pass
