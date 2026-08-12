import "server-only";

import type { ClearHistoryResult } from "@/lib/types";
import { clearHistory as purge } from "@/server/repository/history";
import { insertAudit } from "@/server/repository/transitions";

/**
 * Clear history — hard-delete all resolved (REPLAYED/DISCARDED) messages.
 *
 * Deliberately overrides the soft-delete default: this purges message documents
 * for retention. The audit ledger is kept — its whole point is to outlive the
 * messages it describes — and the purge itself is recorded as one global entry.
 */
export async function clearHistory(actor: string): Promise<ClearHistoryResult> {
  const deleted = await purge();
  await insertAudit(null, {
    action: "CLEAR_HISTORY",
    actor,
    result: "OK",
    detail: { deleted },
  });
  return { deleted };
}
