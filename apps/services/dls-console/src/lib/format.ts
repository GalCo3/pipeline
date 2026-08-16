// Domain-free display helpers.

export function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

/** Compact relative age, e.g. "3m", "5h", "2d". */
export function relAge(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** `cargo-lexical.files` -> `cargo-lexical` — the service that failed. */
export function serviceOf(sourceTopic: string | null | undefined): string {
  return (sourceTopic ?? "").split(".", 1)[0] || "—";
}

/**
 * The payload's own id — what an operator actually recognizes a record by.
 *
 * The Mongo `_id` is the API's identity and means nothing to anyone reading a
 * screen, so the message header leads with the business id instead. Case is not
 * agreed across the pipeline's producers (`id`, `ID`, `Id`, `iD`), and some send
 * `_id`, so all of them are accepted in that order; anything non-scalar is
 * ignored rather than stringified into `[object Object]`.
 */
export function payloadId(payload: unknown): string | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  const record = payload as Record<string, unknown>;
  for (const key of ["id", "ID", "Id", "iD", "_id"]) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" || typeof value === "bigint") return String(value);
  }
  return null;
}

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
