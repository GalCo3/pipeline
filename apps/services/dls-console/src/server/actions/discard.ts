import "server-only";

import { ensureNew, notFound, notNew } from "@/lib/errors";
import type { DiscardResult } from "@/lib/types";
import { loadMessage } from "@/server/repository/messages";
import { insertAudit, markDiscarded } from "@/server/repository/transitions";

/**
 * Discard — soft-delete + audit. Never removes the document.
 *
 * The consumer already committed the offset when it dead-lettered, so there is
 * nothing to undo on Kafka's side: discard is purely a Mongo state change.
 */
export async function discard(
  messageId: string,
  actor: string,
  options: { reason?: string | null; bulkId?: string | null } = {},
): Promise<DiscardResult> {
  const doc = await loadMessage(messageId);
  if (!doc) throw notFound();
  ensureNew(doc);

  if (!(await markDiscarded(messageId, actor))) {
    throw notNew("DISCARDED"); // lost a concurrent transition race
  }

  await insertAudit(messageId, {
    action: "DISCARD",
    actor,
    result: "OK",
    detail: options.reason ? { reason: options.reason } : {},
    bulkId: options.bulkId,
  });
  return { status: "DISCARDED" };
}
