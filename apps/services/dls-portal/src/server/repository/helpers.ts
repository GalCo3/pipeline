import "server-only";

import { ObjectId, type Collection, type Document } from "mongodb";

import { config } from "@/lib/config";
import { db } from "@/lib/mongo";
import { STATUSES, type GroupSummary, type Status, type StatusCounts } from "@/lib/types";

/**
 * Shared repository building blocks: collections, aggregation stages, shapers.
 *
 * The `dls` collection is the pipeline's own dead letter store, written by every
 * service through `hermes.utils.send_to_dls` and read — plus annotated with
 * triage state — here. It is not a sink-built projection: these are the exact
 * documents the services wrote, which is why their fields are snake_case and
 * why nothing in this app ever rewrites them.
 */

/** The pipeline's collection. Shared with the writers. */
export const dls = (): Collection<Document> => db().collection(config.mongo.collection);
/** Portal-owned. `dls` is shared with the pipeline; these two are not. */
export const audit = (): Collection<Document> => db().collection("audit");
export const bulks = (): Collection<Document> => db().collection("bulks");

/**
 * A DLS document has no status until an action touches it, and the stamp pass
 * deliberately never writes one — so "no status field" has to read as NEW
 * everywhere, in aggregation as well as in application code.
 */
export const STATUS_EXPR = { $ifNull: ["$status", "NEW"] };

export function now(): Date {
  return new Date();
}

function countStage(status: Status) {
  return { $sum: { $cond: [{ $eq: [STATUS_EXPR, status] }, 1, 0] } };
}

export function countsGroup(): Record<string, unknown> {
  return Object.fromEntries(STATUSES.map((s) => [s, countStage(s)]));
}

/**
 * First/last failure timestamps for a group of DLS documents.
 *
 * One document per failure, so the document count *is* the occurrence count —
 * there is nothing to sum. The pipeline never merges repeats.
 */
export function seenGroup(): Record<string, unknown> {
  return {
    count: { $sum: 1 },
    firstSeenAt: { $min: "$failed_at" },
    lastSeenAt: { $max: "$failed_at" },
  };
}

export function shapeCounts(doc: Document): StatusCounts {
  return Object.fromEntries(STATUSES.map((s) => [s, doc[s] ?? 0])) as StatusCounts;
}

/** Match one status, treating a missing field as NEW. */
export function statusFilter(status: string | null | undefined): Document {
  if (!status) return {};
  if (status === "NEW") return { $or: [{ status: "NEW" }, { status: { $exists: false } }] };
  return { status };
}

/**
 * Mongo value -> string | null, for fields the API declares as strings.
 *
 * Nothing constrains what a service puts in `error`: it is `str(exc)` for an
 * exception, but a call site may hand `send_to_dls` an arbitrary value. Coerce
 * on read so one odd document degrades to "no text" instead of breaking the
 * whole listing.
 */
export function asText(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string") return value || null;
  if (typeof value === "object") return null;
  return String(value);
}

export function asDate(value: unknown): string | null {
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return null;
}

export function shapeGroup(doc: Document): GroupSummary {
  return {
    fingerprint: doc._id as string,
    errorType: asText(doc.errorType),
    messageSample: asText(doc.messageSample),
    counts: shapeCounts(doc),
    count: (doc.count as number) ?? 0,
    firstSeenAt: asDate(doc.firstSeenAt),
    lastSeenAt: asDate(doc.lastSeenAt),
  };
}

/** Parse an id from the URL. Invalid ids are "not found", never a 500. */
export function objectId(value: string | null | undefined): ObjectId | null {
  if (!value || !ObjectId.isValid(value)) return null;
  return new ObjectId(value);
}
