# Finance spend assistant

A small web app where a finance analyst asks questions about vendor invoices and a procurement policy excerpt, and gets an answer together with the evidence it is based on. FastAPI backend, React frontend, a local model through Ollama.

The idea: **code computes, the model explains, the UI shows receipts.** The model never does arithmetic and never writes quotes. Numbers come from pandas, policy text is copied from the policy file, and every answer is checked against its evidence before it is shown.

## Which LLM path I took

A local model through **Ollama**: `qwen2.5:7b-instruct` (about 4.7 GB). No API key and no stub in the app. The fake model used by the tests lives in `backend/tests/` only. Every response reports the model and the prompt version that produced it.

## Quick start

You need Python 3 (tested with 3.12.12), Node (tested with v26.13.0; Vite 8 needs 20.19 or 22.12 and up) and [Ollama](https://ollama.com) running.

```
ollama pull qwen2.5:7b-instruct
```

Terminal 1, the backend (run it from `backend/`, because the module is `app.main`):

```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

Terminal 2, the frontend:

```
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Vite listens on `localhost`, so if `127.0.0.1` does not work, use `localhost`. The dev server forwards `/summary` and `/ask` to the backend on port 8000, so the backend needs no CORS setup.

- **Speed.** Answers take a few seconds, up to about 20 s for longer questions. The first question after a pause can take 30 to 40 s while Ollama loads the model.
- **Settings.** Optional. A `.env` file at the repository root, or real environment variables (which win over the file): `OLLAMA_MODEL=qwen2.5:7b-instruct` and `OLLAMA_HOST=http://localhost:11434`.
- **Tests.** `cd backend && python -m pytest`. 36 tests, a few seconds, no Ollama needed. Pytest prints one warning from Starlette: `Using httpx with starlette.testclient is deprecated; install httpx2 instead`. I left it. Replacing the dependency late adds more risk than the warning costs.
- **Eval.** `cd backend && python eval/run_eval.py tune` (or `heldout`). Needs Ollama running, takes about 2 minutes, and is not part of the pytest suite. Results are below.
- **Checked from a fresh clone:** the backend install and the 36 tests, and the frontend `npm ci` and `npm run build`. The full app against Ollama was run from my working copy.

## How it works

![How a question becomes a checked answer: the browser, the Vite proxy, the FastAPI backend with its six steps, and the two calls to the local model](docs/architecture.svg)

1. **Plan:** the model turns the question into a small JSON plan (a route, a data query, policy section ids). It writes no code. *Model call 1.*
2. **Validate:** code checks the plan against an allowlist of columns, operators, values and policy sections. A rejected plan goes back to the model once.
3. **Execute:** pandas runs the query on the CSV data, and the policy text is copied from the file by section id.
4. **Compose:** the model sees the question and only the evidence, and writes a short answer with citations. *Model call 2.*
5. **Verify:** numbers, citations and the per-currency rule are checked. A failed check swaps in a plain answer built from the evidence (the fallback).
6. **Respond:** the answer, the evidence, the checks and the model and prompt version go back to the browser.

`GET /summary` is plain pandas, with no model involved.

**The API**
- `GET /summary`: invoice count, spend per currency, spend per currency and vendor status, and how many invoices have no PO number or no approver.
- `POST /ask` with `{"question": "..."}` returns `answer`, `declined`, `route` (data, policy, both or out_of_scope), `evidence` (policy sections with their exact text, and the data rows with how they were computed), `checks` and `meta` (backend, model, prompt version, stub flag, `fallback_used`). An empty or over-long question (more than 500 characters) is a 422. A model that is not running is a 503 with a clear message.

**Rules the code enforces**
- **Amounts in different currencies are never added together.** Policy 5.1 converts at the ECB rate on the invoice date, and I do not have those rates, so totals are per currency and a "top 5" is a top 5 per currency (up to 15 rows). Totals are net of credit notes.
- **A missing PO number or approver is a real value.** It is counted, grouped and shown as "missing", never dropped.
- **The model's plan is data, not code.** It is checked against an allowlist before pandas runs anything. Nothing the model writes is executed.
- **When it cannot answer, it says so.** Out-of-scope questions, plans that stay invalid after one retry, and queries that match no invoices are declined with a reason. For example, policy 7 (who requested a purchase) cannot be checked because the data has no requester field.
- **Text from data fields is untrusted.** The UI shows it as plain text, and the prompts tell the model that evidence is data, not instructions.

## Write-up

### 1. What I built and what I left out

I built the whole path from a question to a checked answer with its evidence: the six steps above, a summary panel, a chat panel and an evidence panel. I put my time into grounding and failure handling, not polish: a verifier with four checks, a fallback answer, declines, and tests that I proved fail when the code is broken (12 deliberate breaks, all caught, by a one-off script that is not kept in the repo), and a small eval set with a scoring script (20 questions, results below).

Left out, and why: auth, deployment, CI/CD and Docker (the brief says not to); a vector database (the policy is about 50 lines and fits in context); streaming, chat history, a cancel button and polish (not needed to show the design); a currency rate table (I have no ECB rates, and invented ones would give numbers I could not defend).

### 2. How I would evaluate it

I built a small version of this (see "Eval results"). At full size:

- **A question set with answers computed independently in pandas:** about 40 data, policy, both and should-decline questions, plus adversarial ones (instructions hidden in the question or in a data field). Mine has 20.
- **Score:** route accuracy, whether the executed result equals the true result (not text matching), section recall, decline precision and recall, the verification pass rate and fallback rate, and latency (median and 95th percentile). All of these are in the scoring script.
- **Hallucinations:** the verifier already rejects invented numbers, numbers from the wrong source and missing citations. It cannot see a wrong answer built from true numbers. The eval confirmed this, so "verified but wrong" is tracked by hand as its own metric.
- **A tuning set kept apart from a held-out set,** rerun on every prompt or model change, with a second reviewer for the by-hand verdicts.

### 3. What production would need

- **200 users:** one local model serves one request at a time, and each question needs two calls. Use a hosted model or a GPU service behind a queue, with caching, rate limits and latency monitoring.
- **Real data:** a database, not CSV files loaded at startup, and ECB rates by invoice date (policy 5.1), so totals and the EUR approval tiers (policy 3) work for GBP and USD. Many policies would need retrieval.
- **Audit trail (policy 8.2):** log per question the user, time, question, plan, executed query, evidence rows or a data snapshot id, answer, checks, and the model, prompt and code versions. Append-only, kept 10 years (policy 8.1).
- **Access control:** single sign-on, roles and row-level limits (by cost center or entity), so the evidence only shows permitted rows. Agree what data may go to an external model.
- **Cost:** two calls per question. Use a small model for planning, cache repeats, set token budgets and alerts.
- **Safety:** with real data, instructions inside description fields become a real risk. Keep validated plans and the verifier, and gate releases on the question set in CI.

## Eval results

20 questions in `backend/eval/questions.json`: ten tuning and ten held-out. The true answers come from `backend/eval/truth.py`, which reads the CSV files with pandas and imports nothing from the app, so a bug in the app's query code cannot also sit in the answer key. `backend/eval/run_eval.py` runs the real pipeline and scores each answer. It checks automatically the route, whether it declined when it should, whether the expected policy sections were cited, and whether the evidence rows equal the true rows (rows, not answer text). Whether the written answer is complete and not misleading is judged by hand, because the verifier cannot judge it. Those verdicts are in `backend/eval/manual_review.json`, and every response is saved in `backend/eval/results/`.

I split the questions so that I could fix problems on one half and report the other half honestly. In the end I fixed nothing: no app code and no prompt changed because of the eval, so neither half was tuned on. The only change was one expected section on a tuning question (5.1 for "total spend in EUR"), which I had set too strictly. The tuning table shows the score as it was run.

| | Tuning (10) | Held-out (10) |
|---|---|---|
| Route correct | 9/10 | 10/10 |
| Evidence rows equal the true rows | 6/7 | 3/5 |
| Expected policy sections cited | 2/3 | 1/3 |
| Declined when it should | 1/1 | 2/3 |
| Questions answered (not declined) | 9 | 8 |
| Passed the verifier, no fallback | 7 of 9 | 7 of 8 |
| Of those, fully right by hand | 4 of 7 | 3 of 7 |
| Fallback used | 2/10 | 1/10 |
| Latency, median and 95th percentile | 7.6 s, 26.3 s | 8.7 s, 19.6 s |

The 26.3 s is the first question, which includes loading the model. The tuning set was run twice and gave the same routes and fallbacks, because the temperature is 0.

**"Passed the verifier" does not mean "right".** The verifier checks numbers and citations, not meaning. On the held-out set, 4 of the 7 answers that passed were not fully right. This is the limit I expected, now measured.

**What the eval found.** All of these are documented, none is fixed:
- **"Who approved the biggest purchase of 2025?" was answered wrongly** (held-out). The plan summed amounts per approver, so the answer named r.okafor with a USD total of 456,887.26, which is not a purchase. The true answer is a different approver in each currency. Every number was real, so it passed.
- **The PO numbers cannot be shown on request** (held-out). "List the purchases of Stellar Facilities Mgmt and what are the PO numbers?" listed all 11 invoices correctly and left out the PO numbers, because the rows carry fixed columns plus the filter columns only.
- **The plan cannot sort by date** (tuning). "Which invoice has the latest invoice date?" returned the largest invoice per currency, because `sort` always means the amount. The receipts say "Ordered by amount", but the answer does not match the question.
- **A decline for the wrong reason** (tuning). "How many invoices were paid within 60 days of receipt?" is declined, because the data has no payment date. But the app got there because the plan was invalid twice, and the message says "try rephrasing", which would send the user in circles.
- **A question that should be declined was answered** (held-out). "Which original invoices do the credit notes belong to?" has no answer in the data. The model wrote that the credit notes belong to original invoices and named the credit notes themselves. The verifier rejected the sentence because the model dropped the minus sign on the amounts, not because it saw the invented link. The fallback lists the two credit notes and names no original, so nothing false is shown, but it does not say the originals cannot be found.
- **A sentence can leave out a currency while every number stays true** (tuning: "top 3 vendors" and "biggest vendor overall"). The table under the answer is right, the sentence is not complete. The compose prompt says not to list rows when there are more than 3, but this is a prompt rule, not enforced: of the 2 answers with more than 3 rows that kept the model's text, both listed rows anyway (the 11 Stellar invoices, and the top 3 as bullets).
- **Two policy answers were narrower than I expected** (held-out). Both are accurate quotes, but the PO question cites 2.2 and not 2.1, and the ON_HOLD question cites 2.2 and not 4.1.

**How to read these numbers.** Twenty questions is too few for a rate: one question moves a score by 10 points. I wrote the questions knowing where the app is weak, so they probably look worse than a random set. Four held-out questions are close to examples in the plan prompt (the PO policy, the EUR 300,000 approval, the ON_HOLD with no PO, and the self-approval questions), so those may score better than a fresh question would. The injection question is typed into the question and is not an instruction hidden in a data field, which is the real risk. The by-hand verdicts are one reader's judgment.

## What is tested, and what is not

**Tested (36 backend tests, run without Ollama, using a fake model):** summary totals against a hand calculation, the query executor, plan validation, each verifier check, the fallback, the pipeline (a verified answer, an invented number replaced by the fallback, a rejected plan retried once, declines), the `/ask` contract, 422 and 503, startup failing without data, and the `.env` reader. Eight headline tests are listed in `docs/DECISIONS.md`.

**Checked by hand, not automated:** the real model on about 16 questions (read against the data), the frontend build, the evidence panel rendered on the server with hostile sample text, and the screens in a browser.

**Not tested:** answer accuracy as a rate (the 20-question eval is too small for one), automated frontend tests, phone-width layout and other browsers, many users at once, and prompt-injection attempts beyond a single manual try.

**Known limits**
- The short answer can mislead even when every number in it is real. The verifier checks numbers and citations, not meaning.
- The plan cannot sort by date or show a column the question asks for (such as PO numbers), and it can read "who approved the biggest purchase" as a sum per approver. All three were found by the eval and are described under "Eval results".
- A number can be used for the wrong claim inside one source. Numbers written as words, or rounded ("1.5 million"), are not recognised.
- Vendor names, descriptions and cost centers in a filter are not checked against known values. A misspelt vendor returns no rows, and the app says nothing matched.
- The policy approval table is shown as the text of the file, not as a rendered table.
- `approved_by` not equal to a name also counts invoices with no approver.
- The backend is read once at startup, so a changed data file needs a restart.

## Time and next steps

About 5.5 to 6 hours in total, by my own estimate from working time and notes. That is over the 3 to 4 hour box. The backend took the longest, mainly the plan step (getting a 7B model to produce reliable plans) and the query executor.

Next, in order. First the gaps the eval found (the time is my estimate, including tests):
- **Sort by date (about 50 minutes).** Add an optional `sort_by` to the plan (amount or invoice date). Dates can be ranked across currencies, unlike amounts, so a date sort and limit must run across all rows, not per currency. The executor, the verifier flag for per-currency limits and the prompt change.
- **Show a requested column (about 35 minutes).** Add an optional `show_columns` list to the plan, checked against the real column names, so "and what are the PO numbers" works.
- **"Biggest purchase" read as a sum per approver.** This is a plan-meaning problem, not a missing field. It needs plan guidance for a single invoice versus a total. I did not add a prompt example for it, because it is a held-out question and teaching it would make the result meaningless. I would first write new held-out questions of the same kind.
- **Declines.** When a plan fails twice, say the question may need data that does not exist, instead of "try rephrasing". Decide on purpose how the number check treats the sign of credit notes.
- **Per-currency sentences.** Check that a lead for a multi-currency result mentions every currency, or build that sentence in code.
- **A bigger eval:** 40 questions, a second reviewer for the verdicts, and an injection test with instructions hidden in a data field.

Then: replacing the `httpx` test dependency (the warning above), real ECB rates, a cancel button, frontend tests, and phone and cross-browser checks.

## How AI was used

I built this with Claude Code in VS Code, in small reviewed steps. I set the architecture and the rules in `CLAUDE.md`, made the design decisions, reviewed each piece, tested the screens and made the commits. The assistant wrote most of the code and explained each piece. The log records what was generated, what I changed or rejected, and what went wrong.

- `CLAUDE.md`: the working agreement and the architecture. I wrote the final draft, refined with Claude from a preflight conversation, before any code.
- `docs/AI_USAGE.md`: what was asked, what was generated, what was changed or got wrong, and what was verified, for each milestone.
- `docs/DECISIONS.md`: the decisions and the alternatives I considered.
- `docs/PROMPTS.md`: the key prompts to the assistant (summaries, with the opening prompt word for word), and the prompts the app sends to the model.
- `backend/prompts/`: the prompts the app sends to the model, as versioned files (`plan_v1` to `plan_v3`, `compose_v1` and `compose_v2`). The versions in use are `plan_v3` and `compose_v2`.

## Project layout

```
backend/app/       data.py, plan.py, validate.py, execute.py, verify.py, fallback.py,
                   render.py, llm.py, pipeline.py, policy.py, settings.py, schemas.py, main.py
backend/prompts/   the prompts sent to the model
backend/tests/     36 tests and a fake model (tests only)
backend/eval/      questions.json, truth.py, run_eval.py, manual_review.json, results/
frontend/src/      api.js and the Summary, Chat and Evidence components
data/              the invoices, vendor master and policy excerpt
docs/              AI_USAGE.md, DECISIONS.md, PROMPTS.md, architecture.svg (the diagram)
```
