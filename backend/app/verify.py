import re
from decimal import Decimal

from app.schemas import Check, DataResult, Evidence

# Numbers like 60,000 or 1,576,971.22 or 5.2. A comma counts only as a thousands
# separator, and a dot only when digits follow it, so "60,000." ends cleanly.
NUMBER_PATTERN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
CITATION_PATTERN = re.compile(r"\[[^\]]*\]")  # anything in square brackets
POLICY_CITATION_PATTERN = re.compile(r"\[policy ([^\]]+)\]")
# Split after . ! ? and a space, unless a citation follows ("... invoices. [data]").
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?!\[)")
# Ways an answer can say that a top-N was ranked within each currency.
PER_CURRENCY_PHRASES = ["per currency", "each currency", "by currency"]


def verify_answer(answer: str, question: str, evidence: Evidence) -> list[Check]:
    return [
        check_numbers(answer, question, evidence),
        check_citations(answer, evidence),
        check_answer_is_cited(answer, evidence),
        check_per_currency_stated(answer, evidence),
    ]


def all_passed(checks: list[Check]) -> bool:
    return all(check.passed for check in checks)


def extract_numbers(text: str) -> set[Decimal]:
    return {Decimal(token.replace(",", "")) for token in NUMBER_PATTERN.findall(text)}


def split_sentences(answer: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(answer) if part.strip()]


def data_numbers(data: DataResult) -> set[Decimal]:
    found = {Decimal(len(data.rows)), Decimal(data.matched_invoice_count)}
    found |= extract_numbers(data.how_computed)
    for row in data.rows:
        for value in row.values():
            if isinstance(value, (int, float)):
                found.add(Decimal(str(value)))
            elif isinstance(value, str):
                found |= extract_numbers(value)  # for example the 20099 in INV-20099
    return found


def check_numbers(answer: str, question: str, evidence: Evidence) -> Check:
    """Each sentence may only use numbers from the evidence it cites, or from the question."""
    question_numbers = extract_numbers(question)
    policy_numbers = {section.section_id: extract_numbers(section.text) for section in evidence.policy}
    everything = set(question_numbers)
    for numbers in policy_numbers.values():
        everything |= numbers
    if evidence.data is not None:
        everything |= data_numbers(evidence.data)

    problems = []
    for sentence in split_sentences(answer):
        cited_ids = POLICY_CITATION_PATTERN.findall(sentence)
        cites_data = "[data]" in sentence

        if cited_ids or cites_data:
            allowed = set(question_numbers)
            for section_id in cited_ids:
                allowed |= policy_numbers.get(section_id, set())
            if cites_data and evidence.data is not None:
                allowed |= data_numbers(evidence.data)
        else:
            allowed = everything  # no citation: fall back to all the evidence

        # Citations such as [policy 2.2] contain numbers that are ids, not claims.
        claimed = extract_numbers(CITATION_PATTERN.sub("", sentence))
        unsupported = sorted(claimed - allowed)
        if unsupported:
            listed = ", ".join(str(number) for number in unsupported)
            problems.append(f"{listed} in \"{sentence}\"")

    if problems:
        return Check(
            name="numbers_in_evidence",
            passed=False,
            detail="Not found in the evidence the sentence cites or in the question: " + "; ".join(problems),
        )
    return Check(
        name="numbers_in_evidence",
        passed=True,
        detail="Every number is in the evidence its sentence cites, or in the question.",
    )


def check_citations(answer: str, evidence: Evidence) -> Check:
    given_ids = {section.section_id for section in evidence.policy}
    unknown = [section_id for section_id in POLICY_CITATION_PATTERN.findall(answer) if section_id not in given_ids]
    data_cited_without_data = "[data]" in answer and evidence.data is None

    problems = []
    if unknown:
        problems.append(f"policy sections not in the evidence: {', '.join(unknown)}")
    if data_cited_without_data:
        problems.append("cites [data] but there is no data evidence")

    if problems:
        return Check(name="citations_exist", passed=False, detail="; ".join(problems))
    return Check(name="citations_exist", passed=True, detail="Every cited source is in the evidence.")


def check_per_currency_stated(answer: str, evidence: Evidence) -> Check:
    """A per-currency "top N" read as one list would rank amounts across currencies."""
    if evidence.data is None or not evidence.data.limit_per_currency:
        return Check(name="per_currency_stated", passed=True, detail="No per-currency limit was applied.")

    if any(phrase in answer.lower() for phrase in PER_CURRENCY_PHRASES):
        return Check(name="per_currency_stated", passed=True, detail="The answer says the ranking is per currency.")
    return Check(
        name="per_currency_stated",
        passed=False,
        detail="The result was limited per currency, but the answer does not say the ranking is per currency.",
    )


def check_answer_is_cited(answer: str, evidence: Evidence) -> Check:
    """Every kind of evidence we gave the model must be cited at least once."""
    given_ids = {section.section_id for section in evidence.policy}
    cites_policy = any(section_id in given_ids for section_id in POLICY_CITATION_PATTERN.findall(answer))

    missing = []
    if evidence.data is not None and "[data]" not in answer:
        missing.append("[data]")
    if evidence.policy and not cites_policy:
        missing.append("a [policy ...] section")

    if missing:
        return Check(name="answer_is_cited", passed=False, detail="The answer does not cite " + " or ".join(missing) + ".")
    return Check(name="answer_is_cited", passed=True, detail="The answer cites each kind of evidence it was given.")
