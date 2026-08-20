import "server-only";

import type { Document } from "mongodb";

import type { GroupSummary } from "@/lib/types";
import { countsGroup, dls, seenGroup, shapeGroup } from "@/server/repository/helpers";

/**
 * Error-group aggregation over two different identities, both surfaced on the
 * one merged overview screen now:
 *
 * - Scoped to a topic filter, groups on the topic-scoped `fingerprint` (`fp:`).
 * - Unscoped (no topic filter), groups on the topic-independent
 *   `errorFingerprint` (`efp:`), so one error hitting N topics collapses to
 *   one row instead of N.
 *
 * The grouping key is projected back as `fingerprint` in both cases, so the UI
 * keys/expands/bulk-acts on a single field regardless of which one produced
 * the row. See `messages.messageFilter` for the either-field match that makes
 * that shared key resolve correctly when a group is expanded.
 */

/** Everything but `_id` — the caller supplies the identity to fold on. */
function groupAccumulators(): Record<string, unknown> {
  return {
    errorType: { $first: "$errorType" },
    // The normalized text, not the raw one: the sample of a group whose
    // members differ only by an interpolated id would otherwise show one
    // arbitrary id as if it were the error.
    messageSample: { $first: "$errorNormalized" },
    // Cross-topic view only: how many source topics this error spans.
    topics: { $addToSet: "$source_topic" },
    ...countsGroup(),
    ...seenGroup(),
  };
}

function shapeCrossTopicGroup(doc: Document): GroupSummary {
  return {
    ...shapeGroup(doc),
    topicCount: (doc.topics as unknown[] | undefined)?.length ?? 0,
  };
}

/** Error groups within one source topic, keyed on the topic-scoped `fingerprint`. */
export async function groupsInTopic(sourceTopic: string): Promise<GroupSummary[]> {
  const docs = await dls()
    .aggregate([
      { $match: { source_topic: sourceTopic } },
      { $group: { _id: "$fingerprint", ...groupAccumulators() } },
      { $sort: { lastSeenAt: -1 } },
    ])
    .toArray();
  return docs.map(shapeGroup);
}

/** Error groups across every source topic, keyed on `errorFingerprint`. */
export async function allGroups(): Promise<GroupSummary[]> {
  const docs = await dls()
    .aggregate([
      { $group: { _id: "$errorFingerprint", ...groupAccumulators() } },
      { $sort: { lastSeenAt: -1 } },
    ])
    .toArray();
  return docs.map(shapeCrossTopicGroup);
}
