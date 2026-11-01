import { Fragment } from "react";

import { formatAmount } from "../format.js";

const MAX_ROWS_SHOWN = 50;
const AMOUNT_COLUMNS = ["amount", "total_amount"];

// Plain-language names for the checks the backend reports.
const CHECK_LABELS = {
  plan_validated: "The plan used only known columns, operators, values and policy sections",
  plan_repaired: "The plan was adjusted by a fixed rule",
  numbers_in_evidence: "Every number in the answer is in the evidence it cites",
  citations_exist: "Every cited source exists in the evidence",
  answer_is_cited: "The answer cites each kind of evidence it was given",
  per_currency_stated: "A per-currency ranking says it is per currency",
};

// The answer cites [data] and [policy 3]. Each block below carries the same tag.
export default function EvidencePanel({ evidence, checks, meta }) {
  const hasEvidence = evidence.policy.length > 0 || evidence.data !== null;

  return (
    <div className="evidence">
      <h3>What this answer is based on</h3>
      {!hasEvidence && <p>No evidence was used.</p>}

      {evidence.data !== null && <DataEvidence data={evidence.data} />}
      {evidence.policy.map((section) => (
        <PolicyEvidence key={section.section_id} section={section} />
      ))}

      <Checks checks={checks} />
      <MetaLine meta={meta} />
    </div>
  );
}

function PolicyEvidence({ section }) {
  return (
    <details open className="evidence-block">
      <summary>
        <span className="tag">[policy {section.section_id}]</span> Policy text, exactly as written
      </summary>
      <pre className="policy-text">{section.text}</pre>
    </details>
  );
}

function DataEvidence({ data }) {
  return (
    <details open className="evidence-block">
      <summary>
        <span className="tag">[data]</span> Invoice data
      </summary>
      <p>{data.how_computed}</p>
      <p>{data.matched_invoice_count} invoices matched.</p>
      {data.rows.length === 0 ? <p>No rows.</p> : <RowsTable rows={data.rows} />}
    </details>
  );
}

function RowsTable({ rows }) {
  const columns = Object.keys(rows[0]);
  const shown = rows.slice(0, MAX_ROWS_SHOWN);
  // A result in several currencies gets a heading row per currency, so each block reads on its own.
  const groupByCurrency = columns.includes("currency") && new Set(rows.map((row) => row.currency)).size > 1;
  let previousCurrency = null;

  return (
    <>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} className={AMOUNT_COLUMNS.includes(column) ? "number" : undefined}>
                  {column.replaceAll("_", " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, index) => {
              const startsNewCurrency = groupByCurrency && row.currency !== previousCurrency;
              previousCurrency = row.currency;
              return (
                <Fragment key={index}>
                  {startsNewCurrency && (
                    <tr className="group-row">
                      <td colSpan={columns.length}>Currency {row.currency}</td>
                    </tr>
                  )}
                  <tr>
                    {columns.map((column) => (
                      <td key={column} className={AMOUNT_COLUMNS.includes(column) ? "number" : undefined}>
                        <Cell column={column} value={row[column]} />
                      </td>
                    ))}
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > MAX_ROWS_SHOWN && (
        <p>
          Showing the first {MAX_ROWS_SHOWN} of {rows.length} rows.
        </p>
      )}
    </>
  );
}

function Cell({ column, value }) {
  if (value === null) return <em>missing</em>; // a missing PO or approver is a real value
  if (typeof value === "number" && AMOUNT_COLUMNS.includes(column)) return formatAmount(value);
  return String(value);
}

function Checks({ checks }) {
  if (checks.length === 0) return null;

  const passedCount = checks.filter((check) => check.passed).length;
  const failedFirst = [...checks].sort((a, b) => Number(a.passed) - Number(b.passed));

  return (
    <details open className="evidence-block">
      <summary>
        Checks: {passedCount} of {checks.length} passed
      </summary>
      <ul className="checks">
        {failedFirst.map((check, index) => (
          <li key={`${check.name}-${index}`} className={check.passed ? "check-pass" : "check-fail"}>
            <strong>{check.passed ? "Passed" : "Failed"}:</strong> {CHECK_LABELS[check.name] ?? check.name}.
            <span className="detail"> {check.detail}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function MetaLine({ meta }) {
  return (
    <p className="meta">
      Model {meta.model} ({meta.backend}), prompt {meta.prompt_version}.{" "}
      {meta.stub && <span className="badge">Stub, not a real model</span>}
    </p>
  );
}
