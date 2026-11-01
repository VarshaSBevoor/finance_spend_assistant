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
