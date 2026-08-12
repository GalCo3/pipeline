import "server-only";

import type { Document } from "mongodb";

import type { BulkStatus, BulkTarget, SharedFields } from "@/lib/types";
import { bulks, dls, now, objectId, statusFilter } from "@/server/repository/helpers";

/**
 * Bulk-action persistence: target resolution + the `bulks` progress collection.
 *
 * Progress lives in Mongo rather than memory so it survives a restart and stays
 * linked to the audit ledger through `bulkId`; counters and per-message results
 * update as the run proceeds, so polling reflects live progress.
 */

// Computing shared fields loads every eligible payload into memory and must be
// exact (a sampled subset could wrongly declare a field "shared"), so we refuse
// rather than sample past this many messages — the UI then falls back to plain
// replay-all for that target.
const SHARED_CAP = 1000;

/** Order-insensitive JSON identity for deep value comparison. */
function canon(value: unknown): string {
  return JSON.stringify(value, (_key, v) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(Object.entries(v as object).sort(([a], [b]) => a.localeCompare(b)))
      : v,
  );
}

/**
 * Message ids for a bulk target. Exactly one selector is expected.
 *
 * - `messageIds`: the explicit selection, verbatim (order preserved) — the
 *   per-message action reports not-found / not-NEW as failed / skipped.
 * - `fingerprint` / `sourceTopic`: the currently-actionable (NEW) members of
 *   that group / topic, so a group or topic bulk doesn't churn through
 *   already-resolved messages.
 */
export async function resolveTarget(target: BulkTarget): Promise<string[]> {
  if (target.messageIds) return [...target.messageIds];

  let query: Document = { ...statusFilter("NEW") };
  if (target.fingerprint) {
    // Either grouping key: a topic-scoped `fingerprint` (topic screen → bulk
    // stays in that topic) or a home `errorFingerprint` (bulk spans topics).
    // `statusFilter` already owns `$or`, so this one goes under `$and`.
    query = {
      $and: [
        query,
        {
          $or: [
            { fingerprint: target.fingerprint },
            { errorFingerprint: target.fingerprint },
          ],
        },
      ],
    };
  } else if (target.sourceTopic) {
    query.source_topic = target.sourceTopic;
  } else {
    return [];
  }

  const docs = await dls()
    .find(query, { projection: { _id: 1 } })
    .sort({ _id: 1 })
    .toArray();
  return docs.map((doc) => String(doc._id));
}

/**
 * Fold one message's payload into the running shared/varying split.
 *
 * `shared === null` marks the first message (the seed). Afterwards a key
 * survives in `shared` only while every message carries it with the same value;
 * the moment one differs or omits it, it moves to `varying` for good.
 */
function intersect(
  shared: Record<string, unknown> | null,
  varying: Set<string>,
  current: Record<string, unknown>,
): Record<string, unknown> {
  if (shared === null) return { ...current };
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(shared)) {
    if (key in current && canon(current[key]) === canon(value)) out[key] = value;
    else varying.add(key);
  }
  // A key seen for the first time on a later message was absent from the seed →
  // it can never be shared.
  for (const key of Object.keys(current)) {
    if (!(key in shared)) varying.add(key);
  }
  return out;
}

/**
 * Top-level payload keys identical across every NEW target message.
 *
 * A key is "shared" only if it is present with the SAME value in ALL eligible
 * messages (deep-compared). The first differing or missing occurrence demotes it
 * to varying. The replay target is each message's own `source_topic`, so it is
 * common only when every message failed on the same topic; otherwise
 * `targetVaries` and the UI offers an explicit redirect instead of a prefill.
 */
export async function computeShared(target: BulkTarget): Promise<SharedFields> {
  const ids = await resolveTarget(target);
  const total = ids.length;
  const empty = {
    tooMany: false,
    payload: {},
    varyingPayloadKeys: [],
    targetTopic: null,
    targetVaries: false,
  };
  if (total === 0) return { total: 0, eligible: 0, ...empty };
  if (total > SHARED_CAP) return { total, eligible: 0, ...empty, tooMany: true };

  const oids = ids.map(objectId).filter((oid) => oid !== null);
  const docs = await dls()
    .find({ _id: { $in: oids } }, { projection: { original_message: 1, source_topic: 1 } })
    .toArray();

  let shared: Record<string, unknown> | null = null;
  const varying = new Set<string>();
  const topics = new Set<string | null>();

  for (const doc of docs) {
    const payload = doc.original_message;
    const asObject =
      payload && typeof payload === "object" && !Array.isArray(payload)
        ? (payload as Record<string, unknown>)
        : {};
    shared = intersect(shared, varying, asObject);
    topics.add((doc.source_topic as string) ?? null);
  }

  const targetVaries = topics.size !== 1;
  return {
    total,
    eligible: docs.length,
    tooMany: false,
    payload: shared ?? {},
    varyingPayloadKeys: [...varying].sort(),
    targetTopic: targetVaries ? null : ([...topics][0] ?? null),
    targetVaries,
  };
}

/** Insert the RUNNING progress document before the background run starts. */
export async function createBulk(
  bulkId: string,
  input: { action: string; actor: string; target: BulkTarget; total: number },
): Promise<void> {
  await bulks().insertOne({
    _id: bulkId as unknown as Document["_id"],
    action: input.action,
    actor: input.actor,
    target: input.target,
    state: "RUNNING",
    total: input.total,
    ok: 0,
    failed: 0,
    skipped: 0,
    results: [],
    createdAt: now(),
    finishedAt: null,
  });
}

/** Push one per-message result and bump its outcome counter atomically. */
export async function appendResult(
  bulkId: string,
  result: { messageId: string; outcome: string; detail: Record<string, unknown> },
): Promise<void> {
  const counter = ["ok", "failed", "skipped"].includes(result.outcome) ? result.outcome : "failed";
  await bulks().updateOne({ _id: bulkId as unknown as Document["_id"] }, {
    $push: { results: { messageId: result.messageId, outcome: result.outcome, ...result.detail } },
    $inc: { [counter]: 1 },
  } as Document);
}

export async function finishBulk(bulkId: string): Promise<void> {
  await bulks().updateOne({ _id: bulkId as unknown as Document["_id"] }, {
    $set: { state: "DONE", finishedAt: now() },
  });
}

export async function getBulk(bulkId: string): Promise<BulkStatus | null> {
  const doc = await bulks().findOne({ _id: bulkId as unknown as Document["_id"] });
  if (!doc) return null;
  return {
    bulkId: String(doc._id),
    action: doc.action,
    state: doc.state,
    total: doc.total,
    ok: doc.ok,
    failed: doc.failed,
    skipped: doc.skipped,
    results: doc.results ?? [],
  };
}
