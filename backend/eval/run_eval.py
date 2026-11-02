"""Run eval questions through the real pipeline and score them.

Usage, from the backend folder:  python eval/run_eval.py tune   (or heldout)

It needs Ollama running. Automatic checks compare the evidence rows with truth.py.
Whether the written answer is complete and not misleading is a manual call, recorded in
eval/manual_review.json, because the verifier cannot judge it.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR.parent))  # so that "app" can be imported

from app.data import load_invoices  # noqa: E402
from app.llm import OllamaLLM  # noqa: E402
from app.pipeline import answer_question  # noqa: E402
from app.policy import load_policy  # noqa: E402
from app.settings import DEFAULT_HOST, DEFAULT_MODEL, get_setting, read_env_file  # noqa: E402
from truth import build_truth  # noqa: E402


def build_llm() -> OllamaLLM:
    file_values = read_env_file()
    return OllamaLLM(
        model=get_setting("OLLAMA_MODEL", DEFAULT_MODEL, file_values),
        host=get_setting("OLLAMA_HOST", DEFAULT_HOST, file_values),
    )


# ---- helpers that read an /ask response ----


def data_rows(response: dict) -> list[dict]:
    data = response["evidence"]["data"]
    if data is None:
        return []
    return data["rows"]


def matched_count(response: dict):
    data = response["evidence"]["data"]
    if data is None:
        return None
    return data["matched_invoice_count"]


def invoice_numbers(response: dict) -> set:
    return {row["invoice_number"] for row in data_rows(response) if "invoice_number" in row}


def totals_by_currency_in_rows(response: dict) -> dict:
    totals = {}
    for row in data_rows(response):
        if "total_amount" in row and "vendor_name" not in row:
            totals[row["currency"]] = round(row["total_amount"], 2)
    return totals


# ---- one comparison per data question: do the evidence rows equal the true result? ----


def check_credit_note_count(response: dict, truth: dict) -> bool:
    return matched_count(response) == truth["count"]


def check_biggest_purchase(response: dict, truth: dict) -> bool:
    for currency, expected in truth.items():
        found = False
        for row in data_rows(response):
            same_invoice = row.get("invoice_number") == expected["invoice_number"]
            same_approver = row.get("approved_by") == expected["approved_by"]
            if row.get("currency") == currency and same_invoice and same_approver:
                found = True
        if not found:
            return False
    return True


def check_stellar(response: dict, truth: dict) -> bool:
    expected = {fact["invoice_number"] for fact in truth["invoices"]}
    rows_have_po_column = all("po_number" in row for row in data_rows(response))
    return invoice_numbers(response) == expected and rows_have_po_column


def check_totals(response: dict, truth: dict) -> bool:
    expected = {currency: round(total, 2) for currency, total in truth["totals_by_currency"].items()}
    return totals_by_currency_in_rows(response) == expected


def check_invoice_list(response: dict, truth: dict) -> bool:
    return invoice_numbers(response) == set(truth["invoice_numbers"])


def check_count(response: dict, truth: dict) -> bool:
    return matched_count(response) == truth["count"]


def check_latest_invoice(response: dict, truth: dict) -> bool:
    expected = {fact["invoice_number"] for fact in truth["invoices"]}
    return invoice_numbers(response) == expected


def check_top_vendors(response: dict, truth: dict) -> bool:
    expected = set()
    for currency, vendors in truth.items():
        for vendor in vendors:
            expected.add((vendor["vendor_name"], currency, round(vendor["total"], 2)))
    found = set()
    for row in data_rows(response):
        found.add((row.get("vendor_name"), row.get("currency"), round(row.get("total_amount", 0), 2)))
    return found == expected


def check_eur_total(response: dict, truth: dict) -> bool:
    found = totals_by_currency_in_rows(response)
    if "EUR" not in found:
        return False
    for currency, total in found.items():
        if total != round(truth["totals_by_currency"][currency], 2):
            return False
    return True


def check_vendor_leaders(response: dict, truth: dict) -> bool:
    for currency, vendor in truth["top_vendor_per_currency"].items():
        found = False
        for row in data_rows(response):
            if row.get("currency") == currency and row.get("vendor_name") == vendor:
                found = True
        if not found:
            return False
    return True


# question id -> comparison. A missing id means "judged by hand" (policy, decline and probe questions).
DATA_CHECKS = {
    "credit_note_count": check_credit_note_count,
    "biggest_purchase_approver": check_biggest_purchase,
    "stellar_purchases_and_pos": check_stellar,
    "on_hold_total": check_totals,
    "on_hold_no_po_and_policy": check_invoice_list,
    "count_q2": check_count,
    "latest_invoice": check_latest_invoice,
    "uk_vendor_spend": check_totals,
    "top3_vendors": check_top_vendors,
    "total_in_eur": check_eur_total,
    "break_highest_currency": check_totals,
    "break_biggest_vendor_overall": check_vendor_leaders,
}


# ---- scoring one question ----


def answer_has_number(answer: str, number: float) -> bool:
    return f"{number:.2f}" in answer.replace(",", "")


def score_question(question: dict, response: dict, truth_all: dict) -> dict:
    declined = response["declined"]
    truth = truth_all.get(question["id"])

    route_ok = question["expected_route"] == "any" or response["route"] == question["expected_route"]
    decline_ok = declined == question["should_decline"]

    sections_ok = None
    if question["expected_sections"] and not question["should_decline"]:
        cited = {section["section_id"] for section in response["evidence"]["policy"]}
        sections_ok = set(question["expected_sections"]).issubset(cited)

    data_ok = None
    if question["id"] in DATA_CHECKS and not question["should_decline"]:
        data_ok = False if declined else DATA_CHECKS[question["id"]](response, truth)

    # A number made by adding across currencies must never be in the answer.
    no_mixed_sum = None
    if truth is not None and "wrong_mixed_currency_sum" in truth:
        no_mixed_sum = not answer_has_number(response["answer"], truth["wrong_mixed_currency_sum"])

    fallback_used = response["meta"]["fallback_used"]
    verified = (not declined) and (not fallback_used) and all(check["passed"] for check in response["checks"])

    automatic = [route_ok, decline_ok, sections_ok, data_ok, no_mixed_sum]
    return {
        "id": question["id"],
        "kind": question["kind"],
        "route_ok": route_ok,
        "decline_ok": decline_ok,
        "sections_ok": sections_ok,
        "data_ok": data_ok,
        "no_mixed_sum": no_mixed_sum,
        "declined": declined,
        "fallback_used": fallback_used,
        "verified": verified,
        "seconds": response["seconds"],
        "automatic_pass": all(value is not False for value in automatic),
    }


# ---- run and report ----


def run_split(split: str) -> tuple[list[dict], dict]:
    questions = json.load(open(EVAL_DIR / "questions.json"))
    questions = [question for question in questions if question["split"] == split]
    truth_all = build_truth()
    llm, invoices, policy = build_llm(), load_invoices(), load_policy()

    scores = []
    responses = {}
    for question in questions:
        started = time.time()
        try:
            response = answer_question(question["question"], llm, invoices, policy).model_dump()
        except Exception as error:  # a crash is a result too: record it and carry on
            print(f"  {question['id']}: pipeline error {error!r}")
            continue
        response["seconds"] = round(time.time() - started, 1)
        responses[question["id"]] = response
        scores.append(score_question(question, response, truth_all))
        print(f"  done {question['id']} ({response['seconds']} s)", flush=True)
    return scores, responses


def load_manual_review() -> dict:
    path = EVAL_DIR / "manual_review.json"
    if not path.exists():
        return {}
    return json.load(open(path))


def percent(count: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{count}/{total}"


def count_true(scores: list[dict], field: str) -> str:
    applicable = [score for score in scores if score[field] is not None]
    return percent(sum(1 for score in applicable if score[field]), len(applicable))


def print_report(scores: list[dict], review: dict) -> None:
    print()
    print(f"{'question':32} {'route':6} {'decl':6} {'sect':6} {'data':6} {'mixed':6} {'verif':6} {'fallb':6} {'s':>5}  manual")
    for score in scores:
        verdict = review.get(score["id"], {}).get("verdict", "-")
        cells = []
        for field in ["route_ok", "decline_ok", "sections_ok", "data_ok", "no_mixed_sum", "verified", "fallback_used"]:
            value = score[field]
            cells.append("-" if value is None else ("yes" if value else "NO"))
        print(f"{score['id']:32} " + " ".join(f"{cell:6}" for cell in cells) + f" {score['seconds']:>5}  {verdict}")

    print()
    print("Route correct:          ", count_true(scores, "route_ok"))
    should_decline = [score for score in scores if score["kind"] in ("decline", "adversarial")]
    declined = [score for score in scores if score["declined"]]
    print("Declines (recall):      ", percent(sum(1 for s in should_decline if s["declined"]), len(should_decline)))
    print("Declines (precision):   ", percent(sum(1 for s in declined if s in should_decline), len(declined)))
    print("Sections cited:         ", count_true(scores, "sections_ok"))
    print("Evidence equals truth:  ", count_true(scores, "data_ok"))
    print("No mixed-currency sum:  ", count_true(scores, "no_mixed_sum"))
    print("Verified (no fallback): ", count_true(scores, "verified"))
    print("Fallback used:          ", percent(sum(1 for s in scores if s["fallback_used"]), len(scores)))
    print("All automatic checks:   ", percent(sum(1 for s in scores if s["automatic_pass"]), len(scores)))

    seconds = sorted(score["seconds"] for score in scores)
    if seconds:
        slowest_index = max(0, int(round(0.95 * len(seconds))) - 1)
        print(f"Latency:                 median {seconds[len(seconds) // 2]} s, 95th percentile {seconds[slowest_index]} s")

    reviewed = [score for score in scores if score["id"] in review]
    if reviewed:
        wrong_but_verified = [s for s in reviewed if s["verified"] and review[s["id"]]["verdict"] != "ok"]
        print("Verified but wrong (by hand):", percent(len(wrong_but_verified), len(reviewed)), "reviewed")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("tune", "heldout"):
        print("Usage: python eval/run_eval.py tune|heldout")
        sys.exit(1)
    split = sys.argv[1]

    print(f"Running the '{split}' questions (Ollama must be running)")
    scores, responses = run_split(split)

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"{split}_{stamp}.json"
    out_path.write_text(json.dumps({"scores": scores, "responses": responses}, indent=1, default=str))

    print_report(scores, load_manual_review())
    print(f"\nFull responses saved to {out_path}")


if __name__ == "__main__":
    main()
