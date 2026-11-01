import { useEffect, useRef, useState } from "react";

import { askQuestion } from "../api.js";
import EvidencePanel from "./EvidencePanel.jsx";

const EXAMPLE_QUESTIONS = [
  "What are our top 5 vendors by total spend in 2025?",
  "What is our total spend with vendors based in Spain?",
  "Who is allowed to approve an invoice of EUR 60,000?",
  "How many invoices have no PO number?",
];
const MAX_QUESTION_LENGTH = 500; // the backend refuses longer questions

export default function ChatPanel() {
  const [question, setQuestion] = useState(""); // what is typed in the box
  const [status, setStatus] = useState("empty"); // "empty", "loading", "error" or "answered"
  const [askedQuestion, setAskedQuestion] = useState(""); // the question being answered (kept for Retry)
  const [response, setResponse] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const controllerRef = useRef(null); // the request in flight, so it can be cancelled

  // If the panel leaves the screen while a request is running, cancel it.
  useEffect(() => () => controllerRef.current?.abort(), []);

  function ask(text) {
    const trimmed = text.trim();
    if (!trimmed || status === "loading") return; // one request at a time

    const controller = new AbortController();
    controllerRef.current = controller;
    setAskedQuestion(trimmed);
    setQuestion("");
    setStatus("loading");

    askQuestion(trimmed, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setResponse(data);
        setStatus("answered");
      })
      .catch((error) => {
        if (controller.signal.aborted || error.kind === "cancelled") return;
        setErrorMessage(error.message);
        setStatus("error");
      });
  }

  function handleSubmit(event) {
    event.preventDefault(); // stop the browser from reloading the page
    ask(question);
  }

  const busy = status === "loading";

  return (
    <section className="panel" aria-label="Ask a question">
      <h2>Ask a question</h2>

      <form className="ask-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={MAX_QUESTION_LENGTH}
          placeholder="Ask about the 2025 invoices or the procurement policy"
          aria-label="Question"
        />
        <button type="submit" disabled={busy || !question.trim()}>
          {busy ? "Working..." : "Ask"}
        </button>
      </form>

      <div aria-live="polite">
        {status === "empty" && <EmptyState onPick={ask} />}

        {status !== "empty" && (
          <p className="asked">
            You asked: <strong>{askedQuestion}</strong>
          </p>
        )}

        {status === "loading" && (
          <p>Working on it. The first question after a pause can take 30 seconds while the model loads.</p>
        )}

        {status === "error" && (
          <div className="error" role="alert">
            <p>{errorMessage}</p>
            <button type="button" onClick={() => ask(askedQuestion)}>
              Retry
            </button>
          </div>
        )}

        {status === "answered" && <Answer response={response} />}
      </div>
    </section>
  );
}

function EmptyState({ onPick }) {
  return (
    <div>
      <p>Ask a question about the 2025 invoices or the procurement policy. Every answer shows what it is based on. For example:</p>
      <ul className="examples">
        {EXAMPLE_QUESTIONS.map((example) => (
          <li key={example}>
            <button type="button" onClick={() => onPick(example)}>
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Answer({ response }) {
  return (
    <>
      <div className={response.declined ? "answer declined" : "answer"}>
        {response.declined && <span className="badge">Declined</span>}
        {response.meta.fallback_used && (
          <span className="badge">Built from the evidence, because the model's answer failed a check</span>
        )}
        <p className="answer-text">{response.answer}</p>
      </div>
      <EvidencePanel evidence={response.evidence} checks={response.checks} meta={response.meta} />
    </>
  );
}
