/**
 * API shapes, shared by the route handlers and the browser.
 *
 * One file rather than a generated client: the same process serves both sides,
 * so the contract is a type import instead of a spec + codegen step. Field names
 * are camelCase here even though the DLS documents are snake_case — the
 * translation lives in the repository layer and stops there.
 */

export type Status = "NEW" | "REPLAYED" | "DISCARDED";

export const STATUSES: Status[] = ["NEW", "REPLAYED", "DISCARDED"];

export type StatusCounts = Record<Status, number>;

/** Columns the message list can be sorted by — one shared list for the client's headers and the API's allowlist. */
export const MESSAGE_SORT_KEYS = [
  "errorType",
  "errorMessage",
  "sourceTopic",
  "partition",
  "offset",
  "failedAt",
  "id",
] as const;
export type MessageSortKey = (typeof MESSAGE_SORT_KEYS)[number];
export type MessageSort = { key: MessageSortKey; dir: "asc" | "desc" };

/** Every operator the message grid's column filter menus can send — string, number and date columns each use their own subset. */
export type MessageFilterOperator =
  | "contains"
  | "doesNotContain"
  | "equals"
  | "doesNotEqual"
  | "startsWith"
  | "endsWith"
  | "isEmpty"
  | "isNotEmpty"
  | "isAnyOf"
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "is"
  | "not"
  | "after"
  | "onOrAfter"
  | "before"
  | "onOrBefore";

/** Every column the filter menus can target — the sortable columns, plus `status` (shown, filterable, but not a sort key). */
export type MessageFilterField = MessageSortKey | "status";

export type MessageFilterItem = {
  field: MessageFilterField;
  operator: MessageFilterOperator;
  value?: unknown;
};

/** One per column filter menu, ANDed or ORed together — the grid's own filter model, shaped for the API/URL instead of a UI library's types. */
export type MessageFilterModel = {
  items: MessageFilterItem[];
  logicOperator?: "and" | "or";
};

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export type ErrorInfo = {
  /** the exception class, recovered from the traceback's last line */
  type: string | null;
  /** the service's own `str(exc)` */
  message: string | null;
  /** the same text with ids/timestamps/numbers masked — what groups show */
  normalized: string | null;
};

export type MessageSummary = {
  /** Mongo `_id` — the API identity every route keys on */
  id: string;
  /** "partition:offset" — display only, never an API key */
  kafkaId: string | null;
  /** the topic the failing consumer was reading; also the replay target */
  sourceTopic: string | null;
  fingerprint: string | null;
  status: Status;
  partition: number | null;
  offset: number | null;
  error: ErrorInfo;
  failedAt: string | null;
};

export type MessageDetail = MessageSummary & {
  errorStack: string | null;
  /** the decoded message the consumer choked on — no raw bytes, no headers */
  payload: unknown;
  edited: boolean;
  editedPayload: unknown;
};

export type TopicSummary = {
  sourceTopic: string;
  counts: StatusCounts;
  groups: number;
  count: number;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
};

export type GroupSummary = {
  fingerprint: string;
  errorType: string | null;
  /** the normalized error text */
  messageSample: string | null;
  counts: StatusCounts;
  /** DLS documents in the group — one per failure, so occurrences */
  count: number;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  /** cross-topic view only: how many source topics this error appears in */
  topicCount?: number;
};

export type AuditEntry = {
  id: string;
  action: "REPLAY" | "EDIT_REPLAY" | "DISCARD" | "UNDISCARD";
  actor: string;
  at: string;
  bulkId: string | null;
  result: "OK" | "FAILED";
  error: string | null;
  detail: Record<string, unknown>;
};

export type Stats = {
  totals: StatusCounts;
  /** distinct source topics that have dead-lettered at least once */
  topics: number;
};

export type ReplayResult = {
  status: "REPLAYED";
  edited: boolean;
  targetTopic: string;
  producedPartition: number | null;
  producedOffset: number | null;
};

export type DiscardResult = { status: "DISCARDED" };

export type UndiscardResult = { status: "NEW" };

/** One of the three selectors — error group, whole topic, or a selection. */
export type BulkTarget = {
  fingerprint?: string | null;
  sourceTopic?: string | null;
  messageIds?: string[] | null;
};

/**
 * What a replay may override on the record it produces.
 *
 * `key` and `headers` are supplied rather than restored — a DLS document keeps
 * neither (see `hermes.utils.dls.DLSRecord`), so an empty field means "produce
 * without one", not "produce the original".
 */
export type RecordOverrides = {
  /** the Kafka record key; empty → keyless, which is how the pipeline produces */
  key?: string | null;
  /** extra Kafka headers; `x-dls-replay-of` is always stamped on top */
  headers?: Record<string, string> | null;
  /** redirect; without it a message replays to its own source topic */
  targetTopic?: string | null;
};

export type ReplayInput = RecordOverrides & {
  /** the full replacement payload — its presence is what makes it an edit */
  payload?: unknown;
};

export type BulkEdit = RecordOverrides & {
  /** top-level keys SET on each payload (shallow merge, nested replaced whole) */
  payload?: Record<string, unknown> | null;
};

export type SharedFields = {
  /** NEW messages in the target */
  total: number;
  /** how many were actually inspected (== total unless tooMany) */
  eligible: number;
  /** over the inspection cap → editing disabled */
  tooMany: boolean;
  payload: Record<string, unknown>;
  varyingPayloadKeys: string[];
  targetTopic: string | null;
  targetVaries: boolean;
};

export type BulkAccepted = { bulkId: string; total: number };

export type BulkResultItem = {
  messageId: string;
  outcome: "ok" | "failed" | "skipped";
  error?: string | null;
  producedOffset?: number | null;
};

export type BulkStatus = {
  bulkId: string;
  action: "REPLAY" | "DISCARD" | "UNDISCARD";
  state: "RUNNING" | "DONE";
  total: number;
  ok: number;
  failed: number;
  skipped: number;
  results: BulkResultItem[];
};

export type Health = {
  status: "ok" | "degraded";
  checks: { mongo: "ok" | "down"; kafka: "ok" | "down" };
};
