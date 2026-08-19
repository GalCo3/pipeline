import "server-only";

import type { GroupSummary } from "@/lib/types";
import { countsGroup, dls, seenGroup, shapeGroup } from "@/server/repository/helpers";

/**
 * Error-group aggregation over two different identities:
 *
 * - The topic screen (within one source topic) groups on the topic-scoped
 *   `fingerprint`.
 * - Home "by error" (across all topics) groups on the topic-independent
 *   `errorFingerprint`, so one error hitting N topics collapses to one row.
 *
 * The grouping key is projected back as `fingerprint` in both cases, so the UI
 * keys/expands/bulk-acts on a single field. A topic-screen value only ever lives
 * in one topic (bulk stays topic-scoped); a home value spans topics (bulk spans
 * topics). See `messages.messageFilter` for the either-field match that makes
 * the shared key resolve correctly.
 */

/** Everything but `_id` — the caller supplies the identity to fold on. */
function groupAccumulators() {
  return {
    errorType: { $first: "$errorType" },
    // The normalized text, not the raw one: the raw sample of a group whose
    // members differ only by an interpolated id would show one arbitrary id as
    // if it were the error.
    messageSample: { $first: "$errorNormalized" },
    // An error can span topics; track how many so the home view can flag a
    // cross-cutting failure.
    topics: { $addToSet: "$source_topic" },
    ...countsGroup(),
    ...seenGroup(),
  };
}

function groupStage(key: string) {
  return { _id: `$${key}`, ...groupAccumulators() };
}

export async function groupsInTopic(sourceTopic: string): Promise<GroupSummary[]> {
  const docs = await dls()
    .aggregate([
      { $match: { source_topic: sourceTopic } },
      { $group: groupStage("fingerprint") },
      { $sort: { lastSeenAt: -1 } },
    ])
    .toArray();
  return docs.map(shapeGroup);
}

/**
 * One group by its key, for the group screen's own header.
 *
 * The key belongs to either namespace, so this matches both fields the way
 * `messages.messageFilter` does and groups the survivors into a single row —
 * `$group` on a constant rather than on the key itself, because a cross-topic
 * `efp:` value lives in `errorFingerprint` while a topic-scoped `fp:` lives in
 * `fingerprint`, and grouping on one field would split or drop the other.
 *
 * Independent of the screen's status filter on purpose: the header describes the
 * group, and it would be absurd for the error class to vanish because the
 * operator switched to a filter that currently matches nothing.
 */
export async function groupByKey(fingerprint: string): Promise<GroupSummary | null> {
  const docs = await dls()
    .aggregate([
      { $match: { $or: [{ fingerprint }, { errorFingerprint: fingerprint }] } },
      { $group: { _id: { $literal: fingerprint }, ...groupAccumulators() } },
    ])
    .toArray();
  if (!docs.length) return null;
  return {
    ...shapeGroup(docs[0]),
    topicCount: (docs[0].topics as unknown[] | undefined)?.length ?? 0,
  };
}

/** Error groups across every source topic — the home "by error" grouping. */
export async function allGroups(): Promise<GroupSummary[]> {
  const docs = await dls()
    .aggregate([{ $group: groupStage("errorFingerprint") }, { $sort: { lastSeenAt: -1 } }])
    .toArray();
  return docs.map((doc) => ({
    ...shapeGroup(doc),
    topicCount: (doc.topics as unknown[] | undefined)?.length ?? 0,
  }));
}
