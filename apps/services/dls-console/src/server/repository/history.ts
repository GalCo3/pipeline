import "server-only";

import type { HistoryItem } from "@/lib/types";
import { asDate, dls } from "@/server/repository/helpers";
import { summary } from "@/server/repository/messages";

/**
 * History = resolved messages (REPLAYED + DISCARDED): read + purge.
 *
 * This is the ONLY place that hard-deletes message documents. Everywhere else
 * follows the soft-delete rule; "clear history" is the deliberate exception an
 * operator opts into for retention. NEW messages are never matched here, and the
 * audit ledger is a separate record this never touches.
 *
 * Note what the purge removes: rows in the pipeline's own `hermes.dls`, written
 * by the services themselves, not a console-side copy. That is the intent
 * (retention on that collection is the whole point), but it makes this the one
 * place the console destroys pipeline data — hence no TTL and no implicit
 * trigger, only the operator's type-CLEAR confirmation.
 */

const RESOLVED = { status: { $in: ["REPLAYED", "DISCARDED"] } };

export async function listHistory(
  page = 1,
  pageSize = 50,
): Promise<{ items: HistoryItem[]; total: number }> {
  const total = await dls().countDocuments(RESOLVED);
  const docs = await dls()
    .find(RESOLVED)
    .sort({ resolvedAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)
    .toArray();
  return {
    items: docs.map((doc) => ({
      ...summary(doc),
      resolvedAt: asDate(doc.resolvedAt),
      resolvedBy: (doc.resolvedBy as string) ?? null,
    })),
    total,
  };
}

/** Hard-delete every REPLAYED/DISCARDED message. Returns the count removed. */
export async function clearHistory(): Promise<number> {
  const result = await dls().deleteMany(RESOLVED);
  return result.deletedCount;
}
