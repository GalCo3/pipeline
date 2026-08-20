import "server-only";

import type { Document } from "mongodb";

import type {
  MessageDetail,
  MessageFilterItem,
  MessageFilterModel,
  MessageFilterOperator,
  MessageSort,
  MessageSortKey,
  MessageSummary,
  Status,
} from "@/lib/types";
import { asDate, asText, dls, objectId, statusFilter } from "@/server/repository/helpers";

/**
 * Message queries: list, detail, raw load.
 *
 * Field names in the store are snake_case because the services write them; the
 * API shape is camelCase, and the translation lives in `summary` / `detail` —
 * nothing above this module should know a document field name.
 */

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export type MessageQuery = {
  sourceTopic?: string | string[] | null;
  fingerprint?: string | string[] | null;
  status?: string | string[] | null;
  /** substring match against the message's own Mongo id (hex), not exact */
  id?: string | null;
  q?: string | null;
  /** per-column filters from the message grid's own filter menus */
  filters?: MessageFilterModel | null;
};

/** `MessageSortKey` mapped to the store's own (snake_case) field names. */
const SORT_FIELDS: Record<MessageSortKey, string> = {
  id: "_id",
  errorType: "errorType",
  errorMessage: "error",
  sourceTopic: "source_topic",
  partition: "partition",
  offset: "offset",
  failedAt: "failed_at",
};

/** A filter value may arrive singular (internal callers) or multi (the UI's toggle menus). */
function toArray(value: string | string[] | null | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

/** `MessageSortKey` mapped to the store's field name, for the columns a plain string/number condition can sit on directly. */
const STRING_FIELDS: Partial<Record<MessageSortKey, string>> = {
  errorType: "errorType",
  errorMessage: "error",
  sourceTopic: "source_topic",
};
const NUMBER_FIELDS: Partial<Record<MessageSortKey, string>> = {
  partition: "partition",
  offset: "offset",
};

/** A string column's filter menu operator, translated to the condition Mongo puts on that field. `undefined` means "not this operator" — the item is dropped rather than matching everything. */
function stringCondition(operator: MessageFilterOperator, value: unknown): unknown {
  if (operator === "isEmpty") return { $in: [null, ""] };
  if (operator === "isNotEmpty") return { $nin: [null, ""] };
  if (operator === "isAnyOf") {
    return Array.isArray(value) && value.length ? { $in: value } : undefined;
  }
  const text = typeof value === "string" ? value : value == null ? "" : String(value);
  if (!text) return undefined;
  const escaped = escapeRegex(text);
  switch (operator) {
    case "contains":
      return { $regex: escaped, $options: "i" };
    case "doesNotContain":
      return { $not: { $regex: escaped, $options: "i" } };
    case "equals":
      return { $regex: `^${escaped}$`, $options: "i" };
    case "doesNotEqual":
      return { $not: { $regex: `^${escaped}$`, $options: "i" } };
    case "startsWith":
      return { $regex: `^${escaped}`, $options: "i" };
    case "endsWith":
      return { $regex: `${escaped}$`, $options: "i" };
    default:
      return undefined;
  }
}

/** A number column's filter menu operator (partition/offset). */
function numberCondition(operator: MessageFilterOperator, value: unknown): unknown {
  if (operator === "isEmpty") return { $in: [null] };
  if (operator === "isNotEmpty") return { $ne: null };
  const n = Number(value);
  if (Number.isNaN(n)) return undefined;
  switch (operator) {
    case "=":
      return n;
    case "!=":
      return { $ne: n };
    case ">":
      return { $gt: n };
    case ">=":
      return { $gte: n };
    case "<":
      return { $lt: n };
    case "<=":
      return { $lte: n };
    default:
      return undefined;
  }
}

/**
 * `failedAt`'s filter menu, day-granularity like the grid's own date picker.
 * The store may hold `failed_at` as a real Date or as an ISO string (see
 * `asDate`), so the comparison runs inside `$expr` against `$toDate` rather
 * than the raw field — the same trick the `id` regex match already uses to
 * reach a value `find`'s plain filter syntax can't coerce.
 */
function dateCondition(operator: MessageFilterOperator, value: unknown): Document | null {
  if (operator === "isEmpty") return { failed_at: { $in: [null] } };
  if (operator === "isNotEmpty") return { failed_at: { $ne: null } };
  if (typeof value !== "string" && typeof value !== "number") return null;
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return null;
  const startOfDay = new Date(at.getFullYear(), at.getMonth(), at.getDate());
  const endOfDay = new Date(startOfDay.getTime());
  endOfDay.setDate(endOfDay.getDate() + 1);
  const field = { $toDate: "$failed_at" };
  let expr: Document | null;
  switch (operator) {
    case "is":
      expr = { $and: [{ $gte: [field, startOfDay] }, { $lt: [field, endOfDay] }] };
      break;
    case "not":
      expr = { $or: [{ $lt: [field, startOfDay] }, { $gte: [field, endOfDay] }] };
      break;
    case "onOrAfter":
      expr = { $gte: [field, startOfDay] };
      break;
    case "after":
      expr = { $gte: [field, endOfDay] };
      break;
    case "onOrBefore":
      expr = { $lt: [field, endOfDay] };
      break;
    case "before":
      expr = { $lt: [field, startOfDay] };
      break;
    default:
      return null;
  }
  return { $expr: expr };
}

/** `id`'s filter menu — same substring-against-the-stringified-ObjectId match the `id` query param uses, just reachable per-operator from the grid. */
function idCondition(operator: MessageFilterOperator, value: unknown): Document | null {
  if (operator === "isEmpty") return { _id: { $in: [] } }; // every message has an _id
  if (operator === "isNotEmpty") return {};
  const text = typeof value === "string" ? value : value == null ? "" : String(value);
  if (!text) return null;
  const escaped = escapeRegex(text);
  const regex = operator === "equals" ? `^${escaped}$` : escaped;
  const match = { $expr: { $regexMatch: { input: { $toString: "$_id" }, regex, options: "i" } } };
  return operator === "doesNotContain" || operator === "doesNotEqual" ? { $nor: [match] } : match;
}

/**
 * The `status` column's own filter menu (a `singleSelect` on the grid, not a
 * free-text column) — `is`/`not`/`isAnyOf` over the three statuses, built on
 * the same `statusFilter` every other status match in this app uses, so "NEW"
 * still matches the field's absence rather than a literal `"NEW"` string.
 */
function statusCondition(operator: MessageFilterOperator, value: unknown): Document | null {
  const values = Array.isArray(value) ? value : value == null ? [] : [value];
  const statuses = values.filter((v): v is string => typeof v === "string");
  if (!statuses.length) return null;
  const or = statuses.map((s) => statusFilter(s));
  if (operator === "not") return { $nor: or };
  return { $or: or };
}

/** One filter-menu item -> a Mongo condition document, or `null` for an item with no effect yet (operator picked, value not typed in). */
function columnCondition(item: MessageFilterItem): Document | null {
  const { field, operator, value } = item;
  if (field === "status") return statusCondition(operator, value);
  if (field === "id") return idCondition(operator, value);
  if (field === "failedAt") return dateCondition(operator, value);
  const numberField = NUMBER_FIELDS[field];
  if (numberField) {
    const condition = numberCondition(operator, value);
    return condition === undefined ? null : { [numberField]: condition };
  }
  const stringField = STRING_FIELDS[field];
  if (stringField) {
    const condition = stringCondition(operator, value);
    return condition === undefined ? null : { [stringField]: condition };
  }
  return null;
}

function messageFilter({ sourceTopic, fingerprint, status, id, q, filters }: MessageQuery): Document {
  const query: Document = {};
  const and: Document[] = [];

  const topics = toArray(sourceTopic);
  if (topics.length === 1) query.source_topic = topics[0];
  else if (topics.length > 1) query.source_topic = { $in: topics };

  const fingerprints = toArray(fingerprint);
  if (fingerprints.length) {
    // One shared key drives both group views: a topic-scoped `fingerprint`
    // (topic screen) or a topic-independent `errorFingerprint` (home). Match
    // either field so the same key resolves the right message set — the two hash
    // namespaces (`fp:` / `efp:`) never collide.
    and.push({ $or: [{ fingerprint: { $in: fingerprints } }, { errorFingerprint: { $in: fingerprints } }] });
  }

  const statuses = toArray(status);
  if (statuses.length) and.push({ $or: statuses.map(statusFilter) });

  if (id) {
    // `_id` is a BSON ObjectId, not a string — `$regexMatch` needs it stringified
    // first, which only `$expr` can do inside a plain `find` filter.
    and.push({
      $expr: { $regexMatch: { input: { $toString: "$_id" }, regex: escapeRegex(id), options: "i" } },
    });
  }

  if (q) {
    const rx = { $regex: escapeRegex(q), $options: "i" };
    and.push({ $or: [{ error: rx }, { source_topic: rx }] });
  }

  if (filters?.items.length) {
    const conditions = filters.items.map(columnCondition).filter((c): c is Document => c !== null);
    if (conditions.length) {
      and.push(filters.logicOperator === "or" ? { $or: conditions } : { $and: conditions });
    }
  }

  if (and.length) query.$and = and;
  return query;
}

/**
 * `partition:offset` — where the record sits in the source topic.
 *
 * The DLS record keeps no Kafka key (the consumer hands the handler a decoded
 * value, and `send_to_dls` stores only that), so this is the only coordinate an
 * operator can paste into Kafbat to find the original. Display only: the Mongo
 * `_id` stays the API identity every route keys on.
 */
function kafkaId(doc: Document): string | null {
  const { partition, offset } = doc;
  if (partition === null || partition === undefined) return null;
  if (offset === null || offset === undefined) return null;
  return `${partition}:${offset}`;
}

export function summary(doc: Document): MessageSummary {
  return {
    id: String(doc._id),
    kafkaId: kafkaId(doc),
    sourceTopic: asText(doc.source_topic),
    fingerprint: (doc.fingerprint as string) ?? null,
    status: ((doc.status as Status) || "NEW") as Status,
    partition: (doc.partition as number) ?? null,
    offset: (doc.offset as number) ?? null,
    error: {
      type: asText(doc.errorType),
      message: asText(doc.error),
      normalized: asText(doc.errorNormalized),
    },
    failedAt: asDate(doc.failed_at),
  };
}

export function detail(doc: Document): MessageDetail {
  return {
    ...summary(doc),
    errorStack: asText(doc.error_stack),
    payload: doc.original_message ?? null,
    edited: Boolean(doc.edited),
    editedPayload: doc.editedPayload ?? null,
  };
}

export async function listMessages(
  query: MessageQuery & { page?: number; pageSize?: number; sort?: MessageSort | null },
): Promise<{ items: MessageSummary[]; total: number }> {
  const page = query.page ?? 1;
  const pageSize = query.pageSize ?? 50;
  const filter = messageFilter(query);
  const total = await dls().countDocuments(filter);
  // `_id` breaks every tie (insertion order), so equal-valued rows on any
  // other column still land in a stable, deterministic order across pages.
  const { key, dir } = query.sort ?? { key: "failedAt", dir: "desc" };
  const order = dir === "asc" ? 1 : -1;
  const sortDoc: Document = { [SORT_FIELDS[key]]: order };
  if (key !== "id") sortDoc._id = order;
  const docs = await dls()
    .find(filter)
    .sort(sortDoc)
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();
  return { items: docs.map(summary), total };
}

export async function getMessage(messageId: string): Promise<MessageDetail | null> {
  const oid = objectId(messageId);
  if (!oid) return null;
  const doc = await dls().findOne({ _id: oid });
  return doc ? detail(doc) : null;
}

/** Raw DLS document (not shaped) — actions need the payload and topic. */
export async function loadMessage(messageId: string): Promise<Document | null> {
  const oid = objectId(messageId);
  if (!oid) return null;
  return dls().findOne({ _id: oid });
}

/**
 * The ids adjacent to this one inside its group, for the serial review loop.
 *
 * Same sort as the group listing (`failed_at` descending), so "next" on the
 * message screen means the next row down on the group screen.
 */
export async function neighbours(
  messageId: string,
  fingerprint: string,
  status?: string | string[] | null,
): Promise<{ prev: string | null; next: string | null }> {
  const filter = messageFilter({ fingerprint, status });
  const ids = await dls()
    .find(filter, { projection: { _id: 1 } })
    .sort({ failed_at: -1 })
    .toArray();
  const index = ids.findIndex((doc) => String(doc._id) === messageId);
  if (index === -1) return { prev: null, next: null };
  return {
    prev: index > 0 ? String(ids[index - 1]._id) : null,
    next: index < ids.length - 1 ? String(ids[index + 1]._id) : null,
  };
}
