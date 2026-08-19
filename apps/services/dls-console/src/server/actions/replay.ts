import "server-only";

import type { Document } from "mongodb";

import {
  ensureNew,
  noTarget,
  notFound,
  notNew,
  unencodablePayload,
  upstreamFailed,
} from "@/lib/errors";
import { ProduceError, produce } from "@/lib/kafka/producer";
import type { BulkEdit, ReplayResult } from "@/lib/types";
import { loadMessage } from "@/server/repository/messages";
import { insertAudit, markReplayed } from "@/server/repository/transitions";

/**
 * Replay + Edit & Replay.
 *
 * Flow: load → guard NEW → pick target → encode payload → produce & await ack →
 * transition NEW→REPLAYED → audit. Any failure past the guard writes a FAILED
 * audit entry and leaves the message NEW, so a broken broker never loses a
 * dead letter.
 *
 * There is no routing resolution and no Schema Registry step. A DLS record names
 * the `source_topic` the consumer was reading when the message blew up, so
 * replay means producing it back to that same topic — not a derived one — and
 * the services consume plain JSON, so the payload goes out as encoded JSON
 * bytes. `targetTopic` stays available as an explicit redirect.
 */

/**
 * Where the replay goes: the explicit redirect, else the source topic.
 *
 * A DLS document with no `source_topic` is malformed (the writer always sets
 * it), but it is pipeline-written data, so it fails as a 409 the operator can
 * resolve with a manual target rather than a 500.
 */
function target(doc: Document, targetTopic: string | null | undefined): string {
  if (targetTopic) return targetTopic;
  const sourceTopic = doc.source_topic;
  if (!sourceTopic) throw noTarget();
  return String(sourceTopic);
}

/**
 * Fold a bulk edit into a full-replacement payload value.
 *
 * Returns `null` when the edit doesn't touch the payload, so the caller keeps
 * replay's "null → not edited" semantics untouched.
 */
function applyEdit(doc: Document, edit: BulkEdit): unknown {
  if (!edit.payload || Object.keys(edit.payload).length === 0) return null;
  const base = doc.original_message;
  const asObject = base && typeof base === "object" && !Array.isArray(base) ? base : {};
  return { ...asObject, ...edit.payload };
}

export async function replay(
  messageId: string,
  actor: string,
  options: {
    payload?: unknown;
    targetTopic?: string | null;
    key?: string | null;
    headers?: Record<string, string> | null;
    edit?: BulkEdit | null;
    bulkId?: string | null;
  } = {},
): Promise<ReplayResult> {
  const doc = await loadMessage(messageId);
  if (!doc) throw notFound();
  ensureNew(doc);

  let payload: unknown = options.payload ?? null;
  let targetTopic: string | null = options.targetTopic ?? null;
  let key: string | null = options.key ?? null;
  let headers: Record<string, string> | null = options.headers ?? null;

  // A bulk edit is merged per-message here (over this document's own payload)
  // and can redirect the target, the record key and the headers for the whole
  // batch. Key and headers are batch-wide by construction: the DLS record kept
  // none of its own, so there is no per-message value to merge over.
  if (options.edit) {
    const edited = applyEdit(doc, options.edit);
    if (edited !== null) payload = edited;
    if (options.edit.targetTopic) targetTopic = options.edit.targetTopic;
    if (options.edit.key) key = options.edit.key;
    if (options.edit.headers) headers = options.edit.headers;
  }

  const topic = target(doc, targetTopic);
  const edited = payload !== null;
  const action = edited ? "EDIT_REPLAY" : "REPLAY";
  const effective = edited ? payload : doc.original_message;

  let value: Buffer;
  try {
    const encoded = JSON.stringify(effective);
    if (encoded === undefined) throw new Error("payload serializes to undefined");
    value = Buffer.from(encoded, "utf8");
  } catch (error) {
    // A payload Mongo accepted but JSON cannot express (BSON-only types).
    const message = error instanceof Error ? error.message : String(error);
    await auditFailed(messageId, action, actor, topic, message, options.bulkId);
    throw unencodablePayload(message);
  }

  let produced;
  try {
    produced = await produce(topic, value, messageId, { key, headers });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await auditFailed(messageId, action, actor, topic, message, options.bulkId);
    if (error instanceof ProduceError) throw upstreamFailed(message);
    throw upstreamFailed(message);
  }

  if (!(await markReplayed(messageId, actor, { edited, editedPayload: payload }))) {
    throw notNew("REPLAYED"); // lost a concurrent transition race
  }

  const detail: Record<string, unknown> = {
    targetTopic: topic,
    producedPartition: produced.partition,
    producedOffset: produced.offset,
  };
  // Only when set — an audit entry that says `key: null` on every ordinary
  // replay reads as "the operator cleared the key" rather than "there wasn't one".
  if (key) detail.key = key;
  if (headers && Object.keys(headers).length) detail.headers = headers;
  if (edited) {
    detail.payloadBefore = doc.original_message;
    detail.payloadAfter = payload;
  }
  await insertAudit(messageId, {
    action,
    actor,
    result: "OK",
    detail,
    bulkId: options.bulkId,
  });

  return {
    status: "REPLAYED",
    edited,
    targetTopic: topic,
    producedPartition: produced.partition,
    producedOffset: produced.offset,
  };
}

async function auditFailed(
  messageId: string,
  action: string,
  actor: string,
  targetTopic: string,
  error: string,
  bulkId?: string | null,
): Promise<void> {
  await insertAudit(messageId, {
    action,
    actor,
    result: "FAILED",
    detail: { targetTopic },
    error,
    bulkId,
  });
}
