import re

from app.llm import PLAN_PROMPT, PROMPTS_DIR
from app.policy import POLICY_FILE, load_policy


def test_policy_sections_are_exact_text_from_the_file():
    policy_text = POLICY_FILE.read_text()
    sections = load_policy()

    for section_id, text in sections.items():
        assert text in policy_text, f"section {section_id} is not verbatim"

    assert sections["2.2"].startswith("2.2 Invoices received without a valid PO reference")
    assert "| 50,000.01 – 250,000 | Finance Director |" in sections["3"]


def test_prompt_menu_lists_exactly_the_policy_section_ids():
    prompt = (PROMPTS_DIR / f"{PLAN_PROMPT}.txt").read_text()
    menu = prompt.split("POLICY SECTIONS")[1].split("RULES")[0]
    menu_ids = set(re.findall(r"^(\d+(?:\.\d+)?) ", menu, re.M))

    assert menu_ids == set(load_policy())
