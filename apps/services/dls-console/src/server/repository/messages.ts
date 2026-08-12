import "server-only";

import type { Document } from "mongodb";

import type { MessageDetail, MessageSummary, Status } from "@/lib/types";
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
  sourceTopic?: string | null;
  fingerprint?: string | null;
  status?: string | null;
  q?: string | null;
};

function messageFilter({ sourceTopic, fingerprint, status, q }: MessageQuery): Document {
  const query: Document = {};
  const and: Document[] = [];
  if (sourceTopic) query.source_topic = sourceTopic;
  if (fingerprint) {
    // One shared key drives both group views: a topic-scoped `fingerprint`
    // (topic screen) or a topic-independent `errorFingerprint` (home). Match
    // either field so the same key resolves the right message set — the two hash
    // namespaces (`fp:` / `efp:`) never collide.
    and.push({ $or: [{ fingerprint }, { errorFingerprint: fingerprint }] });
  }
  if (status) and.push(statusFilter(status));
  if (q) {
    const rx = { $regex: escapeRegex(q), $options: "i" };
    and.push({ $or: [{ error: rx }, { source_topic: rx }] });
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
    partition: (doc.partition as number) ?? null,
    offset: (doc.offset as number) ?? null,
    errorStack: asText(doc.error_stack),
    payload: doc.original_message ?? null,
    edited: Boolean(doc.edited),
    editedPayload: doc.editedPayload ?? null,
  };
}

export async function listMessages(
  query: MessageQuery & { page?: number; pageSize?: number },
): Promise<{ items: MessageSummary[]; total: number }> {
  const page = query.page ?? 1;
  const pageSize = query.pageSize ?? 50;
  const filter = messageFilter(query);
  const total = await dls().countDocuments(filter);
  const docs = await dls()
    .find(filter)
    .sort({ failed_at: -1 })
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
  status?: string | null,
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
