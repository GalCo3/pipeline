import "server-only";

import { audit, dls, now, objectId, statusFilter } from "@/server/repository/helpers";

/**
 * Write-path Mongo access: state-machine transitions + audit inserts.
 *
 * Triage state is `$set` onto the pipeline's own DLS document rather than kept
 * in a side collection — one collection means `_id` alone stays the API identity
 * and every listing filters/sorts on status without a `$lookup`. The services
 * only ever insert, so the added fields (`status`, `resolvedAt`, `resolvedBy`,
 * `edited*`) are never written over theirs.
 *
 * Transitions guard on "still NEW" in the update filter itself, so concurrent
 * actions cannot double-resolve: the loser matches nothing and its caller
 * reports 409. A document the services just wrote has no `status` field at all,
 * so the guard has to accept the field's absence as NEW.
 */

/** NEW -> REPLAYED. Returns false if the message was no longer NEW (race). */
export async function markReplayed(
  messageId: string,
  actor: string,
  options: { edited: boolean; editedPayload: unknown },
): Promise<boolean> {
  const changes: Record<string, unknown> = {
    status: "REPLAYED",
    resolvedAt: now(),
    resolvedBy: actor,
  };
  if (options.edited) {
    changes.edited = true;
    // `original_message` is never overwritten — the edit is stored beside it, so
    // the document still shows what the service actually received.
    changes.editedPayload = options.editedPayload;
  }
  const result = await dls().updateOne(
    { _id: objectId(messageId)!, ...statusFilter("NEW") },
    { $set: changes },
  );
  return result.matchedCount === 1;
}

/** NEW -> DISCARDED (soft-delete). Returns false if no longer NEW (race). */
export async function markDiscarded(messageId: string, actor: string): Promise<boolean> {
  const result = await dls().updateOne(
    { _id: objectId(messageId)!, ...statusFilter("NEW") },
    { $set: { status: "DISCARDED", resolvedAt: now(), resolvedBy: actor } },
  );
  return result.matchedCount === 1;
}

/**
 * Append one audit document. `messageId` is null for global actions
 * (CLEAR_HISTORY), which belong to no single message.
 */
export async function insertAudit(
  messageId: string | null,
  entry: {
    action: string;
    actor: string;
    result: "OK" | "FAILED";
    detail: Record<string, unknown>;
    error?: string | null;
    bulkId?: string | null;
  },
): Promise<void> {
  await audit().insertOne({
    messageId: messageId === null ? null : objectId(messageId),
    action: entry.action,
    actor: entry.actor,
    at: now(),
    bulkId: entry.bulkId ?? null,
    detail: entry.detail,
    result: entry.result,
    error: entry.error ?? null,
  });
}
