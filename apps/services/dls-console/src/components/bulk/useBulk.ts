"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/client";
import type { BulkEdit, BulkTarget } from "@/lib/types";

/**
 * Bulk run lifecycle: fire the request, hold the ticket, refresh on completion.
 *
 * The 202 ticket is the whole reason this is a hook rather than a mutation — the
 * work outlives the request, so the UI needs somewhere to keep the `bulkId`
 * while the progress modal polls it, and something to invalidate with when the
 * run ends and every count on screen is stale.
 */
export function useBulk() {
  const queryClient = useQueryClient();
  const [bulkId, setBulkId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function launch(promise: Promise<{ bulkId: string }>) {
    setError(null);
    try {
      setBulkId((await promise).bulkId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return {
    bulkId,
    error,
    replay: (target: BulkTarget, edit?: BulkEdit | null) => launch(api.bulkReplay(target, edit)),
    discard: (target: BulkTarget, reason?: string | null) =>
      launch(api.bulkDiscard(target, reason)),
    close: () => setBulkId(null),
    finished: () => {
      setBulkId(null);
      // Everything on screen counted the messages this just resolved.
      queryClient.invalidateQueries();
    },
  };
}
