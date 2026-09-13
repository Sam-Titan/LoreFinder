const BASE_URL = "http://127.0.0.1:8000";

// FastAPI's `detail` is usually a string, but on a 422 it's an array of
// Pydantic validation-error objects — normalize both shapes to one message
// so the UI never renders "[object Object]".
function errorMessage(err, fallback) {
  const detail = err?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map(d => d.msg || JSON.stringify(d)).join("; ");
  }
  return fallback;
}

async function parseError(res, fallback) {
  try {
    const err = await res.json();
    return errorMessage(err, fallback);
  } catch {
    return fallback;
  }
}

// --- Ingestion ---

export async function ingestNovel(novelName, authorName) {
  const res = await fetch(`${BASE_URL}/ingest/novel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ novel_name: novelName, author_name: authorName })
  });
  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to start ingestion."));
  }
  return res.json();
}

export async function ingestPDF(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/ingest/pdf`, {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to upload PDF."));
  }
  return res.json();
}

export async function checkStatus(docId) {
  const res = await fetch(`${BASE_URL}/ingest/status/${docId}`);
  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to check status."));
  }
  return res.json();
}

// --- Query ---

export async function queryDocument(docId, query) {
  const res = await fetch(`${BASE_URL}/query/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_id: docId, query })
  });
  if (!res.ok) {
    throw new Error(await parseError(res, "Query failed."));
  }
  return res.json();
}

// --- Health ---

export async function healthCheck() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

// --- History (localStorage) ---

export function getHistory() {
  try {
    return JSON.parse(localStorage.getItem("dawn_history") || "[]");
  } catch {
    return [];
  }
}

export function addToHistory({ doc_id, title, author, type, status }) {
  const history = getHistory();
  const existing = history.findIndex(h => h.doc_id === doc_id);
  const entry = {
    doc_id, title, author, type, status,
    added_at: new Date().toISOString()
  };
  if (existing >= 0) {
    history[existing] = entry; // update status if already exists
  } else {
    history.unshift(entry);
  }
  localStorage.setItem("dawn_history", JSON.stringify(history.slice(0, 20)));
}

export function removeFromHistory(docId) {
  const updated = getHistory().filter(h => h.doc_id !== docId);
  localStorage.setItem("dawn_history", JSON.stringify(updated));
}

export function clearHistory() {
  localStorage.removeItem("dawn_history");
}