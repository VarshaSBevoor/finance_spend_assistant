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
