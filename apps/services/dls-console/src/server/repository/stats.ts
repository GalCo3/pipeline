import "server-only";

import type { Stats } from "@/lib/types";
import { countsGroup, dls, shapeCounts } from "@/server/repository/helpers";

/**
 * Dashboard stats: the status totals and how many source topics have failed.
 *
 * Deliberately not a top-N of error groups as well. The overview already lists
 * every group under one of its two lenses, and a second ranked list of the same
 * rows on the same screen was a second thing to read rather than a shortcut —
 * so the aggregation behind it is gone too, not just its panel.
 */
export async function stats(): Promise<Stats> {
  const [totalsDoc] = await dls()
    .aggregate([{ $group: { _id: null, ...countsGroup() } }])
    .toArray();

  const topics = await dls().distinct("source_topic");

  return {
    totals: shapeCounts(totalsDoc ?? {}),
    topics: topics.length,
  };
}
