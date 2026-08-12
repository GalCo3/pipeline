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
  error: ErrorInfo;
  failedAt: string | null;
};

export type MessageDetail = MessageSummary & {
  partition: number | null;
  offset: number | null;
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
  /** the consuming service's own lag on this topic; null if unavailable */
  lag: number | null;
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

export type HistoryItem = MessageSummary & {
  resolvedAt: string | null;
  resolvedBy: string | null;
};

export type AuditEntry = {
  id: string;
  action: "REPLAY" | "EDIT_REPLAY" | "DISCARD" | "CLEAR_HISTORY";
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

export type ClearHistoryResult = { deleted: number };

/** One of the three selectors — error group, whole topic, or a selection. */
export type BulkTarget = {
  fingerprint?: string | null;
  sourceTopic?: string | null;
  messageIds?: string[] | null;
};

export type BulkEdit = {
  /** top-level keys SET on each payload (shallow merge, nested replaced whole) */
  payload?: Record<string, unknown> | null;
  /** batch redirect; without it each message replays to its own source topic */
  targetTopic?: string | null;
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
  action: "REPLAY" | "DISCARD";
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
