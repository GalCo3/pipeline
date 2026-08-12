import "server-only";

import type { TopicSummary } from "@/lib/types";
import {
  asDate,
  countsGroup,
  dls,
  seenGroup,
  shapeCounts,
} from "@/server/repository/helpers";

/**
 * Overview aggregation: one row per source topic.
 *
 * Keyed on `source_topic` because it is what replay targets, what consumer lag
 * is measured against, and — since each service consumes its own topic — which
 * service failed. There is no `service` field on a DLS record, and there should
 * not be one: the topic already says it.
 */
export async function topicsSummary(): Promise<Omit<TopicSummary, "lag">[]> {
  const docs = await dls()
    .aggregate([
      {
        $group: {
          _id: "$source_topic",
          fingerprints: { $addToSet: "$fingerprint" },
          ...countsGroup(),
          ...seenGroup(),
        },
      },
      { $sort: { _id: 1 } },
    ])
    .toArray();

  return docs.map((doc) => ({
    sourceTopic: doc._id as string,
    counts: shapeCounts(doc),
    groups: (doc.fingerprints as unknown[] | undefined)?.length ?? 0,
    count: (doc.count as number) ?? 0,
    firstSeenAt: asDate(doc.firstSeenAt),
    lastSeenAt: asDate(doc.lastSeenAt),
  }));
}
