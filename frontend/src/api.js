// The only place that talks to the backend. Components call getSummary and
// askQuestion and never use fetch directly, so errors look the same everywhere.

const SUMMARY_TIMEOUT_MS = 15000;
// Longer than the backend's own 120 s wait for the model, so the backend's
// clear "took too long" message arrives before this timer gives up.
const ASK_TIMEOUT_MS = 150000;

export class ApiError extends Error {
  // kind lets the screen decide what to do: "cancelled" is ignored, the rest are shown.
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }
}

export function getSummary(signal) {
  return request("/summary", { signal, timeoutMs: SUMMARY_TIMEOUT_MS });
}

export function askQuestion(question, signal) {
  return request("/ask", { method: "POST", body: { question }, signal, timeoutMs: ASK_TIMEOUT_MS });
}

async function request(path, { method = "GET", body, signal, timeoutMs }) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  // The caller can cancel too, for example when a component is removed from the screen.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  try {
    const response = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!response.ok) throw await shapeHttpError(response);

    try {
      return await response.json();
    } catch {
      throw new ApiError("server", "The server sent a response that could not be read.");
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (timedOut) throw new ApiError("timeout", "The request took too long. The model may still be loading, so try again.");
    if (error.name === "AbortError") throw new ApiError("cancelled", "The request was cancelled.");
    throw new ApiError("network", "Cannot reach the server. Is the backend running?");
  } finally {
    clearTimeout(timer);
  }
}

async function shapeHttpError(response) {
  if (response.status === 503) {
    // The backend explains what is down, for example "Cannot reach Ollama. Is it running?"
    return new ApiError("unavailable", (await readDetail(response)) || "The service is unavailable.");
  }
  if (response.status === 502 || response.status === 504) {
    // A proxy in front of the backend (the Vite dev server here) answers like this when the backend is down.
    return new ApiError("network", "Cannot reach the backend. Is it running?");
  }
  if (response.status === 422) {
    return new ApiError("rejected", "That question was not accepted. Use between 1 and 500 characters.");
  }
  return new ApiError("server", `The server returned an error (status ${response.status}).`);
}

async function readDetail(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}
