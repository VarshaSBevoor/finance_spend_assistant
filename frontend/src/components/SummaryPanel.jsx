import { useEffect, useState } from "react";

import { getSummary } from "../api.js";
import { formatAmount } from "../format.js";

export default function SummaryPanel() {
  const [status, setStatus] = useState("loading"); // "loading", "error" or "loaded"
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [attempt, setAttempt] = useState(0); // changing this runs the effect again, which is how Retry works

  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");

    getSummary(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return; // an older request must not overwrite a newer one
        setSummary(data);
        setStatus("loaded");
      })
      .catch((error) => {
        if (controller.signal.aborted || error.kind === "cancelled") return;
        setErrorMessage(error.message);
        setStatus("error");
      });

    // Runs when the component leaves the screen or the effect runs again.
    return () => controller.abort();
  }, [attempt]);

  return (
    <section className="panel" aria-label="Summary">
      <h2>Summary</h2>
      {status === "loading" && <p>Loading summary...</p>}

      {status === "error" && (
        <div className="error" role="alert">
          <p>{errorMessage}</p>
          <button type="button" onClick={() => setAttempt(attempt + 1)}>
            Retry
          </button>
        </div>
      )}

      {status === "loaded" && <SummaryContent summary={summary} />}
    </section>
  );
}

function SummaryContent({ summary }) {
  if (summary.invoice_count === 0) {
    return <p>No invoices are loaded.</p>;
  }

  return (
    <>
      <p>
        <strong>{summary.invoice_count}</strong> invoices. Amounts are never added across currencies, and totals are net of
        credit notes.
      </p>

      <h3>Spend by currency</h3>
      <table>
        <thead>
          <tr>
            <th>Currency</th>
            <th className="number">Total</th>
            <th className="number">Invoices</th>
          </tr>
        </thead>
        <tbody>
          {summary.spend_by_currency.map((row) => (
            <tr key={row.currency}>
              <td>{row.currency}</td>
              <td className="number">{formatAmount(row.total)}</td>
              <td className="number">{row.invoice_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>By vendor status</h3>
      <table>
        <thead>
          <tr>
            <th>Currency</th>
            <th>Vendor status</th>
            <th className="number">Total</th>
            <th className="number">Invoices</th>
          </tr>
        </thead>
        <tbody>
          {summary.spend_by_currency_and_status.map((row) => (
            <tr key={`${row.currency}-${row.vendor_status}`}>
              <td>{row.currency}</td>
              <td>{row.vendor_status}</td>
              <td className="number">{formatAmount(row.total)}</td>
              <td className="number">{row.invoice_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Missing values</h3>
      <ul>
        <li>{summary.missing_po_count} invoices have no PO number.</li>
        <li>{summary.missing_approver_count} invoices have no approver.</li>
      </ul>
    </>
  );
}
