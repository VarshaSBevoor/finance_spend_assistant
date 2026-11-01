// Amounts as 1,576,971.22, the same way the backend writes them in its answers.
export function formatAmount(value) {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
