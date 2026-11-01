import re
from pathlib import Path

POLICY_FILE = Path(__file__).resolve().parents[2] / "data" / "procurement_policy.md"


def load_policy(path: Path = POLICY_FILE) -> dict[str, str]:
    """Section id -> exact text from the policy file, e.g. "2.2" or "3".

    Clauses like "2.2 ..." are single lines, kept as written. A top-level
    section such as "3" has no id line of its own, so its text is the body
    under the heading (here, the approval table) up to the first clause.
    """
    sections: dict[str, list[str]] = {}
    heading_id = None  # the top-level section whose body we are collecting

    for line in path.read_text().splitlines():
        heading = re.match(r"^## (\d+)\.", line)
        clause = re.match(r"^(\d+\.\d+) ", line)

        if heading:
            heading_id = heading.group(1)
        elif clause:
            sections[clause.group(1)] = [line]
            heading_id = None  # a clause ends the heading's own body
        elif line.strip() and heading_id is not None:
            sections.setdefault(heading_id, []).append(line)

    return {section_id: "\n".join(lines) for section_id, lines in sections.items()}
