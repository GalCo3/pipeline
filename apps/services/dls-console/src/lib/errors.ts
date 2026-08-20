/**
 * Action-layer error -> HTTP mapping.
 *
 * The action layer stays framework-agnostic (testable without a request): it
 * throws `ActionError`, and the route handlers render it through `toResponse`.
 * Status codes follow AGENTS.md -> Actions.
 */

export class ActionError extends Error {
  readonly status: number;
  readonly detail: unknown;
  /** bulk outcome bucket: "skipped" for already-resolved, else "failed". */
  readonly kind: "failed" | "skipped";

  constructor(status: number, detail: unknown, kind: "failed" | "skipped" = "failed") {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
    this.kind = kind;
  }
}

export const notFound = (what = "message not found") => new ActionError(404, what);

export const notNew = (status: string) =>
  new ActionError(409, `message is ${status}, not NEW — already resolved`, "skipped");

/** Guard: actions only apply to NEW messages. */
export function ensureNew(doc: { status?: string | null }): void {
  const status = doc.status ?? "NEW";
  if (status !== "NEW") throw notNew(status);
}

export const notDiscarded = (status: string) =>
  new ActionError(409, `message is ${status}, not DISCARDED`, "skipped");

/** Guard: undiscard only applies to DISCARDED messages. */
export function ensureDiscarded(doc: { status?: string | null }): void {
  const status = doc.status ?? "NEW";
  if (status !== "DISCARDED") throw notDiscarded(status);
}

/**
 * A DLS document with no `source_topic` — nothing to replay it onto.
 *
 * The writer always sets the field, so this means hand-written or corrupted
 * data; 409 rather than 500 because the operator can still replay it by passing
 * an explicit `targetTopic`.
 */
export const noTarget = () =>
  new ActionError(409, "no source topic on the document — pass an explicit targetTopic");

/** Stored payload that JSON cannot express (BSON-only types). */
export const unencodablePayload = (detail: string) =>
  new ActionError(422, { message: "payload is not JSON-encodable", errors: [detail] });

export const upstreamFailed = (detail: string) => new ActionError(502, detail);

export const unauthorized = () => new ActionError(401, "not authenticated");
