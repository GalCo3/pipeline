import "server-only";

import type { AnyBulkWriteOperation, Document } from "mongodb";

import { FP_VERSION, fingerprints } from "@/lib/fingerprint";
import { audit, dls } from "@/server/repository/helpers";

/**
 * Derived-identity backfill over the pipeline's DLS documents.
 *
 * The services write a DLS record and nothing else — no fingerprint, no status.
 * Grouping needs a hash of the normalized error, and Mongo cannot hash inside an
 * aggregation, so the values are computed here and `$set` back onto the document
 * the first time the console sees it.
 *
 * Stamping rather than computing per request is what keeps the group screens a
 * single `$group` instead of a full scan into application memory: after the
 * first pass every document carries `fingerprint`, and the index on it does the
 * work.
 *
 * Idempotent and bounded: only documents whose stamp is missing or stale are
 * read, in batches, and `ensureStamped` runs at the top of every read path — so
 * a document written a second ago is grouped correctly on the next request
 * without anything having to watch the collection.
 *
 * "Stale" is the second half of that: the stamp carries the `fpVersion` it was
 * derived with, so bumping the recipe re-derives the whole collection over the
 * next few reads instead of leaving one error split across two hashings.
 */

// Per request, not per pass: a burst larger than this is stamped across the next
// few requests rather than holding one of them open. Read paths tolerate an
// unstamped tail (it groups on the following call); a stall does not.
const BATCH = 2_000;

let indexed = false;

/**
 * Create the read-path indexes. Runs once per process, on first read.
 *
 * Deliberately lazy rather than at startup: the pod would otherwise block on
 * Mongo round-trips before it can answer a probe, and a slow store would hold
 * the whole app down. Reads all funnel through `ensureStamped`, so the first one
 * pays for it and every later one skips on the flag.
 *
 * Not `unique` anywhere: the pipeline writes one document per failure and
 * genuinely repeats them, which is the point — the count of documents in a group
 * *is* the occurrence count.
 */
async function ensureIndexes(): Promise<void> {
  if (indexed) return;
  indexed = true;
  await Promise.all([
    dls().createIndex({ fingerprint: 1, status: 1 }),
    dls().createIndex({ errorFingerprint: 1, status: 1 }),
    dls().createIndex({ source_topic: 1, status: 1 }),
    dls().createIndex({ failed_at: 1 }),
    dls().createIndex({ resolvedAt: 1 }),
    // The stamp pass's own filter — without it every read path scans the whole
    // collection to discover there is nothing left to stamp.
    dls().createIndex({ fpVersion: 1 }),
    audit().createIndex({ messageId: 1, at: 1 }),
    audit().createIndex({ bulkId: 1 }),
  ]);
}

async function stampBatch(): Promise<number> {
  const cursor = dls()
    .find(
      { fpVersion: { $ne: FP_VERSION } },
      { projection: { error: 1, error_stack: 1, source_topic: 1 } },
    )
    .limit(BATCH);

  const operations: AnyBulkWriteOperation<Document>[] = [];
  for await (const doc of cursor) {
    operations.push({
      updateOne: {
        filter: { _id: doc._id },
        // Identity only. `status` is deliberately NOT written here: absence
        // means NEW everywhere (see `helpers.STATUS_EXPR`), so a stamp pass
        // racing an operator's discard can never revive a resolved document.
        update: {
          $set: fingerprints({
            error: doc.error,
            errorStack: doc.error_stack,
            sourceTopic: doc.source_topic,
          }),
        },
      },
    });
  }
  if (operations.length === 0) return 0;
  const result = await dls().bulkWrite(operations, { ordered: false });
  return result.modifiedCount;
}

/**
 * Stamp every unstamped DLS document. Returns how many were written.
 *
 * Best-effort: a failure here degrades grouping for the newest documents, so it
 * is logged and swallowed rather than 500-ing a read the operator needs.
 */
export async function ensureStamped(): Promise<number> {
  try {
    await ensureIndexes();
    return await stampBatch();
  } catch (error) {
    console.warn("DLS stamping failed", error);
    return 0;
  }
}
