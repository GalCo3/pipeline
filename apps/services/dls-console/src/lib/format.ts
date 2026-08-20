// Domain-free display helpers.

/** DD/MM/YYYY, 24-hour time — explicit rather than the browser's locale, so it reads the same for every operator regardless of where they are. */
const TS_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return TS_FORMAT.format(date);
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

/** Thousands-separated exact count, e.g. `2,287,867`. */
export function fullNum(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US");
}

/**
 * Count shortened to fit a fixed-width column, e.g. `5,980`, `151k`, `2.1M`.
 *
 * The list columns are sized for a glance, not for an audit: a raw 49887885 is
 * wider than any column that still leaves room for the topic name, so it used to
 * spill over its neighbour. Below 10k the exact number still fits, so it is kept
 * — the shortening only starts where the digits stop being readable anyway. The
 * exact value stays one hover away on the `title` of every caller.
 */
export function compactNum(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value < 0 ? "-" : "";
  const n = Math.abs(value);
  if (n < 10_000) return sign + n.toLocaleString("en-US");
  for (const [limit, suffix] of [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "k"],
  ] as Array<[number, string]>) {
    if (n < limit) continue;
    const scaled = n / limit;
    // One decimal only while it buys precision — "9.9M" reads, "151.2k" does not
    // fit and does not matter at that size.
    return sign + (scaled < 10 ? scaled.toFixed(1) : Math.round(scaled).toString()) + suffix;
  }
  return sign + n.toLocaleString("en-US");
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
