# How I used AI to build this

Tools: Claude Code in VS Code. Model path used while running the app: see README.

Working agreement: see `CLAUDE.md`. I asked for one small piece at a time, with a plain explanation, and I made the git commits myself.

## Log
Add an entry after each milestone.

| Milestone | What I asked for | What was generated | What I changed or rejected, and why | Something it got wrong that I caught |
|---|---|---|---|---|
| M0 | Read CLAUDE.md and the brief, restate the task, propose milestones. Pick an Ollama model. Profile the data. Set up the backend folders and dependencies. | A milestone plan with time budgets. A data profile (140 rows, 21 blank PO, 25 blank approver, 2 negative amounts, every vendor in 3 currencies). A model recommendation. A venv with fastapi, uvicorn, pydantic, pandas, httpx, pytest. | (you fill in: I agreed to no rate table and httpx) | CLAUDE.md pointed to `reference/assignment_brief.pdf` but the file is at the project root. The Ollama setup prompt was not attached the first time. |
| M1 | Data loader, summary schemas, `build_summary`, two tests, then `main.py` with `GET /summary` and a test. I wrote the first draft of `main.py` myself in "my turn" mode. | `data.py`, `schemas.py`, `summary.py`, `tests/test_summary.py`, `tests/test_main.py`, and a corrected `main.py` with comments. | (you fill in: what you changed after review) | My first `.gitignore` review was right to flag `data/`, but I only caught the unsaved `main.py` (0 bytes) by running pytest. Draft of `main.py` used `lifespan=load_invoices`, which is wrong, and reloaded the CSVs on every request. |

## What I wrote myself
(Fill in at the end, honestly.)

## What I verified
(Tests run, hand calculations compared with the app, checks on the data.)
- M0: counted rows, blanks, negatives, currencies and statuses with a short stdlib script. No tests exist yet.
- M1: `build_summary` compared with an independent exact-decimal calculation on the real CSV (all 3 currency totals and 9 currency-and-status rows matched). Saved tests: 3 passed (hand-calculated frame, missing PO and approver, `/summary` on the real data). Not done: breaking the code on purpose to confirm tests fail, and a test that startup fails on a missing data file.
