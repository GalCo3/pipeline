import "server-only";

import { ensureDiscarded, ensureNew, notDiscarded, notFound, notNew } from "@/lib/errors";
import type { DiscardResult, UndiscardResult } from "@/lib/types";
import { loadMessage } from "@/server/repository/messages";
import { insertAudit, markDiscarded, markUndiscarded } from "@/server/repository/transitions";

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

/**
 * Undiscard — the one reversible transition, single-message only. Puts a
 * discarded message back in the operator's NEW queue; the discard's own
 * audit entry (and any reason it carried) stays put as the historical record.
 */
export async function undiscard(
  messageId: string,
  actor: string,
  options: { bulkId?: string | null } = {},
): Promise<UndiscardResult> {
  const doc = await loadMessage(messageId);
  if (!doc) throw notFound();
  ensureDiscarded(doc);

  if (!(await markUndiscarded(messageId))) {
    throw notDiscarded(doc.status ?? "NEW"); // lost a concurrent transition race
  }

  await insertAudit(messageId, {
    action: "UNDISCARD",
    actor,
    result: "OK",
    detail: {},
    bulkId: options.bulkId,
  });
  return { status: "NEW" };
}
