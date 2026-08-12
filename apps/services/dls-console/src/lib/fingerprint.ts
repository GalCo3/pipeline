import { createHash } from "node:crypto";

/**
 * Error identity: normalize a DLS `error` string, then hash it two ways.
 *
 * The pipeline writes one DLS document per failure — no dedup, no grouping — so
 * grouping is entirely the console's job. It keys on the exception text, which is
 * the only failure description a DLS record carries (`error` = `str(exc)`,
 * `error_stack` = the formatted traceback).
 *
 * Normalizing first is what makes the grouping useful: the same bug reads as a
 * hundred distinct strings once ids, offsets and timestamps are interpolated
 * into it. Strip those and "document 4a1f… not found in bucket cargo" collapses
 * onto "document <id> not found in bucket cargo".
 *
 * Two hashes, because the UI groups at two altitudes:
 *
 * - `fingerprint` = sha1(type + normalized + source topic), `fp:`-prefixed —
 *   topic-scoped, drives the per-topic screen.
 * - `errorFingerprint` = sha1(type + normalized), `efp:`-prefixed —
 *   topic-independent, so one error hitting N topics collapses to one home row.
 *
 * The prefixes keep the two namespaces from colliding, which is what lets a
 * single `fingerprint` path parameter resolve against either field.
 */

/**
 * Recipe version, stamped beside the hashes.
 *
 * The fingerprint is persisted, so a change to the recipe would otherwise leave
 * the collection half-hashed one way and half the other — one error reading as
 * two groups depending on when its document happened to be stamped. Bumping
 * this is what makes `ensureStamped` re-derive every document that still
 * carries an older recipe.
 */
export const FP_VERSION = 3;

// Order matters only in that the specific patterns run before the general number
// sweep — a UUID or an ISO timestamp would otherwise be shredded into fragments
// by it and stop matching itself across occurrences.
const SUBSTITUTIONS: Array<[RegExp, string]> = [
  [/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, "<id>"],
  [/\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/g, "<ts>"],
  [/\b[0-9a-f]{16,}\b/gi, "<hash>"],
  [/0x[0-9a-f]+/gi, "<addr>"],
  [/\b\d+\b/g, "<n>"],
];

// `str(exc)` on its own drops the class, so the type is recovered from the last
// line of the traceback — "module.ValueError: boom" -> ValueError.
const TRACEBACK_LINE = /^([A-Za-z_][\w.]*)\s*:\s?.*$/;

/**
 * Collapse an echoed payload to `<obj>`.
 *
 * A validator that fails prints the object it choked on — pydantic's
 * `input_value={'id': 4, 'name': 'bob', ...}` — which makes the message unique
 * per document and the group a list of one. The braces are what mark it as
 * data rather than description, so the whole brace-delimited span goes and
 * everything around it (the field, the constraint, the model) stays.
 *
 * Innermost-out, repeatedly, because these nest; capped so a message with
 * unbalanced braces cannot spin.
 */
function maskObjects(text: string): string {
  let out = text;
  for (let depth = 0; depth < 8; depth++) {
    const next = out.replace(/\{[^{}]*\}/g, "<obj>");
    if (next === out) break;
    out = next;
  }
  return out;
}

function escapeRe(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Mask the writer's own identity out of its error text.
 *
 * Every service in the pipeline interpolates its own name into the message —
 * `Failed to index cargo-lexical document 4` — so the same bug in six services
 * reads as six distinct strings and the topic-independent `errorFingerprint`
 * never collapses anything, which is exactly what the "by error" lens exists to
 * do. The tokens masked are taken from `source_topic` rather than matched by
 * shape, so a hyphenated word that merely looks like a slug ("read-only",
 * "not-found") survives untouched.
 *
 * The topic goes first: `cargo-lexical.files` contains `cargo-lexical`, and
 * masking the service first would leave a stray `<svc>.files` behind.
 */
function maskWriter(text: string, sourceTopic: string | null | undefined): string {
  const topic = (sourceTopic ?? "").trim();
  if (!topic) return text;
  const tokens: Array<[string, string]> = [
    [topic, "<topic>"],
    [topic.split(".", 1)[0], "<svc>"],
  ];
  let out = text;
  for (const [token, replacement] of tokens) {
    // Two chars is not an identity, it is a coincidence waiting to happen.
    if (token.length < 3) continue;
    out = out.replace(new RegExp(`(?<![\\w-])${escapeRe(token)}(?![\\w-])`, "gi"), replacement);
  }
  return out;
}

/**
 * Error text with the writing service, echoed payloads, ids, timestamps, hashes
 * and numbers masked out.
 */
export function normalize(error: string | null | undefined, sourceTopic?: string | null): string {
  // Writer identity before the generic sweeps: a topic like `chat-rooms-v2`
  // would otherwise come out of the number sweep as `chat-rooms-v<n>` and stop
  // matching its own name. Echoed payloads go next, whole, so the sweeps below
  // never have to make sense of their contents.
  let text = maskObjects(maskWriter((error ?? "").trim(), sourceTopic));
  for (const [pattern, replacement] of SUBSTITUTIONS) {
    text = text.replace(pattern, replacement);
  }
  return text.replace(/\s+/g, " ").trim();
}

/**
 * Exception class name, from the last frame of the traceback.
 *
 * Falls back to an `error` string that happens to be shaped `Type: message`
 * (some call sites hand `send_to_dls` a plain string, in which case there is no
 * stack at all).
 */
export function errorType(
  errorStack: string | null | undefined,
  error?: string | null,
): string | null {
  for (const source of [errorStack, error]) {
    const lines = (source ?? "").trim().split("\n");
    for (let i = lines.length - 1; i >= 0; i--) {
      const match = TRACEBACK_LINE.exec(lines[i].trim());
      if (match) return match[1].split(".").pop() ?? null;
    }
  }
  return null;
}

function sha1(...parts: string[]): string {
  // Grouping identity, not a security primitive — sha1 is short and fast.
  return createHash("sha1").update(parts.join("\x1f"), "utf8").digest("hex");
}

export type Fingerprints = {
  errorType: string | null;
  errorNormalized: string;
  fingerprint: string;
  errorFingerprint: string;
  fpVersion: number;
};

/** The full derived-identity set stamped onto a DLS document. */
export function fingerprints(input: {
  error?: string | null;
  errorStack?: string | null;
  sourceTopic?: string | null;
}): Fingerprints {
  const normalized = normalize(input.error, input.sourceTopic);
  const kind = errorType(input.errorStack, input.error) ?? "";
  return {
    errorType: kind || null,
    errorNormalized: normalized,
    fingerprint: `fp:${sha1(kind, normalized, input.sourceTopic ?? "")}`,
    errorFingerprint: `efp:${sha1(kind, normalized)}`,
    fpVersion: FP_VERSION,
  };
}
