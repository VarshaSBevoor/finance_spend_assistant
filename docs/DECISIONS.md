# Decisions

One entry per decision, five lines at most: what I decided, why, what else I considered.

## Template
**Decision:**
**Why:**
**Alternatives considered:**
**Revisit if:**

## Decided before the build
**Decision:** Plan, validate, execute, compose, verify, respond, instead of putting the data in the prompt.
**Why:** The model should not do arithmetic or report its own evidence. Code computes and builds the evidence.
**Alternatives considered:** whole CSV in the prompt; model-written pandas or SQL; a single tool-calling loop; a vector database for a 50-line policy.
**Revisit if:** the question space becomes open-ended (then a tool loop is more flexible).

## M0: data and setup
**Decision:** No currency rate table. Spend is grouped by currency and never added across currencies.
**Why:** Every one of the 10 vendors has invoices in EUR, GBP and USD, so currency belongs to the invoice, not the vendor. Policy 5.1 wants ECB rates on each invoice date, and we do not have them. Inventing rates would produce numbers we cannot defend.
**Alternatives considered:** a fixed rate table recorded as an assumption.
**Revisit if:** real ECB rates are supplied. The policy tiers in section 3 are in EUR, so GBP and USD invoices cannot be matched to a tier without them.

**Decision:** Call Ollama over plain HTTP with `httpx`, not the `ollama` package.
**Why:** One endpoint, and the request sent to `/api/chat` stays visible. httpx gives short timeouts and clear error types.
**Alternatives considered:** the standard library `urllib` (no dependency, more code); the `ollama` package (hides the call).
**Revisit if:** we need streaming or many Ollama features.

**Decision:** Local model `qwen2.5:7b-instruct` (about 4.7 GB) on an M4 with 16 GB.
**Why:** Short plan and compose calls, JSON schema output, no credits, and a reader of the repo needs only one `ollama pull`.
**Alternatives considered:** Ollama cloud models (need sign-in and credits, structured output on cloud not verified); thinking models (reasoning comes back in a separate field).
**Revisit if:** plans are often invalid after the retry. Next try `llama3.1:8b`.

## M1: summary endpoint
**Decision:** Load the data once at startup in a lifespan function and keep it on `app.state`. The route is a plain `def`.
**Why:** A broken data file stops the app at startup, not on a user request. Pandas work is blocking, and FastAPI runs plain `def` routes in a thread pool.
**Alternatives considered:** loading the CSVs per request (simple, wasteful, fails late); a module-level global (harder to test).
**Revisit if:** the data changes while the app runs. Then reload on a schedule or move to a database.

**Decision:** Summary totals are per currency and net of credit notes (2 negative amounts are included).
**Why:** No rate table (see M0). Excluding credit notes would hide real adjustments.
**Alternatives considered:** a separate gross total and credit note total.
**Revisit if:** analysts need gross spend. Add a credit note count to the response.

## M2: the plan step
**Decision:** The model returns a plan (data, not code). Required keys in the schema, cross-field checks in `Plan`, and one retry that shows the model its error.
**Why:** With optional keys, a 7B model skipped `policy_sections` and `filters`, and the plans were valid but wrong. Required keys fixed most of that on the 7 test questions. The checks reject plans whose route has nothing to run.
**Alternatives considered:** a bigger or different model (`llama3.1:8b`, not tried); letting the model write pandas or SQL (rejected for safety); an enum for `column` in the schema (not tried).
**Revisit if:** the eval set shows many valid-but-wrong plans, such as a missing filter. Then try an enum for columns or another model.

**Decision:** Prompts are versioned files (`plan_v1`, `v2`, `v3`) and `PROMPT_VERSION` names the one in use. Old versions stay for comparison.
**Why:** A prompt change changes behaviour. The version in the response meta shows which prompt produced an answer.
**Alternatives considered:** a prompt string in Python code (harder to diff and read); a hash of the file (automatic, more code).
**Revisit if:** we forget to bump the constant. Then use a hash.

**Decision:** Ollama context set to 8192 tokens, temperature 0, one retry, then decline with `PlanError`. An unreachable or slow Ollama is a separate `LLMError`.
**Why:** The default context for this machine is 4k, which is tight with a retry. Temperature 0 makes plans nearly repeatable. A bad plan is a decline, but a down model is an error to show.
**Alternatives considered:** more retries (the model rarely fixes itself on a third try); a larger context (more memory).
**Revisit if:** prompts or evidence grow beyond about 6k tokens.

## M3: validate and execute
**Decision:** `limit` applies per currency whenever the result has a currency column. Results are ordered by currency, then by value. A "top 5 vendors" question returns up to 15 rows (5 per currency).
**Why:** Currencies cannot be ranked against each other without a rate table, and we have none (see M0). Five rows overall would mix currencies.
**Alternatives considered:** one overall top 5 (mixes currencies); converting to EUR (needs ECB rates we do not have).
**Revisit if:** a rate table is supplied.

**Decision:** Grouping keeps missing values as their own group (`dropna=False`). `approved_by ne X` includes invoices with no approver.
**Why:** A missing approver or PO is a real finding under policy 3.1 and 2.2. Dropping it would hide the invoices that need attention.
**Alternatives considered:** SQL-style behaviour, where a missing value drops out of a comparison.
**Revisit if:** analysts find "not approved by X" counts misleading. Then exclude missing values and say so.

**Decision:** The validator rejects bad plans and makes one repair by rule (a sum always groups by currency). Allowed values for currency, status, country and category are read from the data.
**Why:** A rule is predictable. A guess about what the model meant is how a wrong answer slips through. Reading values from the data means they cannot go stale.
**Alternatives considered:** repairing typos and case; typing the value lists into the validator.
**Revisit if:** the retry fails often on case or spelling. Then normalise case before checking.

**Decision:** Free-text columns (vendor_name, description, cost_center, approved_by) are not checked against known values.
**Why:** The sets are larger and change with the data. A misspelt vendor returns no rows, and the answer says "no matching invoices".
**Alternatives considered:** checking vendor names against the master.
**Revisit if:** the eval set shows misspelt names are common.

## M4: compose, verify, respond
**Decision:** Verification is code with four checks: every number in a sentence must come from the evidence that sentence cites (or the question); every cited id must exist; every kind of evidence given must be cited; a per-currency top-N must say it is per currency. A failed check replaces the answer with a template built from the evidence.
**Why:** A model checking a model can fail the same way. Code is exact and repeatable. A failed check gives a safe, plain answer instead of a confident wrong one.
**Alternatives considered:** a second model call as a judge; one global "number appears somewhere" check (it let a policy figure be attributed to data); a rounding tolerance (not built, we measure first).
**Revisit if:** the eval set shows misattribution inside one source, or many fallbacks from harmless wording.

**Decision:** Hybrid answers. For results with more than 3 rows the model writes a short lead and code lists every row, grouped by currency, in order.
**Why:** A verified answer once dropped a vendor and misordered a list, with every number real. Copying a table is mechanical, so code does it. It does not depend on this model's strength, and a stronger model writes a better lead.
**Alternatives considered:** code writes all list answers (wastes a stronger model); a check that every row is mentioned (fragile); leaving it and documenting it.
**Revisit if:** the eval set shows a stronger model lists rows reliably. The threshold is one constant, `LIST_ROW_THRESHOLD`.

**Decision:** A failed plan, an out-of-scope question and a result with no matching invoices are declined with a reason, and `declined: true`. A model that is down is a 503, not a decline.
**Why:** The analyst should see "I will not guess" differently from "the service is down".
**Alternatives considered:** a 400 error for declines; a model-written refusal.
**Revisit if:** the frontend wants more detail on why.

**Decision:** Settings come from real environment variables, then a `.env` file read by a 15-line reader, then defaults. No dependency.
**Why:** CLAUDE.md asks to avoid new dependencies without asking, and `.env` is the file the repo already lists as ignored.
**Alternatives considered:** `python-dotenv`; shell variables only.
**Revisit if:** the format grows beyond `KEY=value` lines.

**Known limits, for the README:** the lead sentence can mislead with true numbers; a number can be used in the wrong claim inside one source; rounded figures and number words are not recognised; free-text columns are not checked against known values; the eval set is not built yet.

## M5: tests
**Decision:** Keep 36 tests and name 8 as the headline tests. The rest are smaller guards for rules the README claims. CLAUDE.md asked for 5 to 8 focused tests, so this is a deliberate extension, agreed on 2026-11-01.
**Why:** Each test protects a different claim (never add across currencies, missing values are real, a failed check uses the fallback). Merging them to reach 8 would mix unrelated assertions and make a failure harder to read.
**Alternatives considered:** trim to 8 (cheapest to explain, least protection); trim to about 30 by merging overlaps (not worth the time).
**Revisit if:** the suite becomes slow or hard to explain. It runs in under a second.

**Headline tests (the 8 to walk through):**
1. `test_summary.py::test_totals_match_hand_calculation_and_stay_per_currency`: summary totals against a hand calculation.
2. `test_execute.py::test_sum_with_filter_groups_by_vendor_and_currency_sorted_within_currency`: the query function on a small frame.
3. `test_validate.py::test_bad_column_value_operator_and_section_are_all_reported`: plan validation rejects a bad column.
4. `test_verify.py::test_an_invented_number_is_caught`: verification catches an invented number.
5. `test_main.py::test_ask_returns_the_contract_shape`: `/ask` returns the contract shape.
6. `test_main.py::test_ask_declines_an_out_of_scope_question`: an out-of-scope question is declined.
7. `test_pipeline.py::test_an_answer_with_an_invented_number_is_replaced_by_the_fallback`: a failed verification uses the fallback.
8. `test_pipeline.py::test_a_rejected_plan_is_retried_once_with_the_reasons_and_then_answered`: a rejected plan is retried once.

**Decision:** The one stretch item is the small eval set with a scoring script. Guardrails (decline when it cannot answer, verify and fall back, 422 and 503) are part of the core pipeline, not the stretch.
**Why:** The brief says "pick one at most". The guardrails cost no extra work. The eval set gives real numbers for the "how you would evaluate" part of the write-up.
**Alternatives considered:** claiming guardrails as the stretch.
**Revisit if:** time runs out. The eval set is the first thing to cut, and the README says so.

## M6: rows are shown as a table, not retyped into the answer
**Decision:** The answer text is the model's short lead only. The rows are not written into it. The UI shows the rows as a table directly under the answer, built from `evidence.data.rows` (code-made, complete, in order), with a heading row per currency when there is more than one. A list of invoices carries 5 core columns (invoice number, date, vendor, amount, currency) plus any column the question filtered on, not all 13.
**Why:** A user test found the retyped rows a wall of `key: value` text that repeated the evidence table and could not be read at a glance. The guarantee is unchanged: the model cannot drop or reorder rows, because it never writes them. A reader scans a table far faster than text.
**Alternatives considered:** keep rows in the answer text (what we had); show all 13 columns (too much); let the model choose columns (can drop the one that matters).
**Revisit if:** an API client needs the rows inside the answer string. They are in `evidence.data.rows`. Hidden columns (description, cost centre, category) are still in the CSV, but not shown in the evidence.

**Decision:** The fallback answer for a long result (more than 3 rows) says "The N result rows are in the evidence table" and does not retype them. Short results (3 rows or fewer) are still written out.
**Why:** Same reason as above, and the fallback must still pass its own verification (N is the number of rows, which is in the evidence).

## M8: eval set
**Decision:** 20 questions: 10 tuning and 10 held-out. The held-out half was fixed before any run and run once. The tuning half was for looking at failures and fixing the app.
**Why:** If we keep only the questions that pass after tuning, the score is inflated. A locked half cannot be gamed by our own fixes.
**Alternatives considered:** one set of about 12 (simpler, but no honest number); a second held-out batch (not needed for the brief, which asks for 5 to 10 pairs).
**Revisit if:** the eval is used to gate releases. Then it needs more questions and a second reviewer.

**Decision:** True answers come from `eval/truth.py`, plain pandas that imports nothing from `app/`. The scorer compares the evidence rows with the true rows, not the answer text.
**Why:** A bug in the app's loader or executor must not also be inside the answer key. Text matching would pass a right-sounding answer with wrong rows.
**Alternatives considered:** reusing the app's executor to compute truth (faster to write, but one bug could be wrong in both places and still pass); comparing numbers in the answer text.
**Revisit if:** the app's query language grows so much that the truth file becomes a second copy of it.

**Decision:** Two levels of scoring. Automatic checks: route, decline, sections, evidence rows, no mixed-currency sum, verified, fallback, latency. By hand: whether the sentence is complete and not misleading, recorded in `manual_review.json`.
**Why:** The verifier cannot judge meaning, and the eval showed it: on the held-out set, 4 of the 7 answers that passed the verifier were not fully right. An automatic score alone would have hidden that.
**Alternatives considered:** another model as the judge (adds a second unreliable model, and it was not wanted); automatic checks only.
**Revisit if:** there are enough questions that by-hand review does not scale. Then use a sampled review with two reviewers.

**Decision:** Three questions from the brief were not used as they are, because they appear word for word as examples in `plan_v3.txt` (top 5 vendors, spend in Spain, who approves EUR 60,000). They were replaced with variants (top 3, the UK, EUR 300,000). Each question has a `seen_in_prompts` field (none, near).
**Why:** Scoring a question the model has seen in its prompt measures memory, not skill. Four held-out questions are still `near` an example, and the README says so.
**Alternatives considered:** keep the brief's questions (they look like the obvious test).
**Revisit if:** the prompt examples change. Then the field must be checked again.

**Decision:** Fix nothing after the eval. The gaps it found are documented in the README with an estimated fix for each.
**Why:** The project was already over the 3 to 4 hour box. Two fixes would have added about 1.5 hours. Changing the plan model, the executor and the prompt the day before sending adds risk with a 7B model. A gap that the eval found and that is explained is a clearer statement than a rushed fix. Stellar (held-out) would also have stopped being held-out after a fix.
**Alternatives considered:** fix the PO column only (about 35 minutes); fix both (about 1 hour 15 minutes, plus a rerun of all 20 questions).
**Revisit if:** the repo is worked on after the interview. The order is in the README under "Time and next steps".

**Decision:** One expected section on a tuning question was removed after run 1 (5.1 for "total spend in EUR"). It is recorded in the question file and in the README.
**Why:** It was my guess, and it was too strict: the answer, a plain EUR total, is correct without it. The tuning table shows the score as it was run.
**Alternatives considered:** leave it and report a failure that was not one.
**Revisit if:** never for held-out. No held-out expectation was changed.

**Known limits found by the eval (all in the README):** the plan cannot sort by date; rows cannot show a column the question asks for (PO numbers); "biggest purchase" can be read as a sum per approver; a plan that fails twice is declined with "try rephrasing", even when the real reason is missing data; a number check that drops the minus sign caught an invented link by luck; a sentence can omit a currency while every number is true.
