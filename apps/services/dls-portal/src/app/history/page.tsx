"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/client";
import { formatTs } from "@/lib/format";
import { ConfirmDialog } from "@/components/Modal";
import {
  Button,
  EmptyState,
  ErrorState,
  Eyebrow,
  Pagination,
  Panel,
  Spinner,
  StatusBadge,
  StatusEdge,
} from "@/components/ui";

/**
 * Resolved messages, newest first — plus the one destructive path in the app.
 *
 * Clear history hard-deletes rows the *pipeline's own services* wrote, not a
 * portal-side copy, so it is gated behind type-CLEAR and never runs on a timer.
 * The audit ledger survives the purge; it may then reference documents that no
 * longer exist, which is the permanent record working as intended.
 */
export default function HistoryPage() {
  const [page, setPage] = useState(1);
  const [confirming, setConfirming] = useState(false);
  const queryClient = useQueryClient();

  const history = useQuery({
    queryKey: ["history", page],
    queryFn: () => api.history({ page }),
  });

  const clear = useMutation({
    mutationFn: api.clearHistory,
    onSuccess: () => {
      setConfirming(false);
      void queryClient.invalidateQueries();
    },
  });

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <Eyebrow>Replayed and discarded</Eyebrow>
          <h1 className="font-display text-2xl font-semibold tracking-tight">History</h1>
        </div>
        <Button
          variant="danger"
          icon={Trash2}
          disabled={!history.data?.total}
          onClick={() => setConfirming(true)}
        >
          Clear history
        </Button>
      </div>

      {clear.error && <ErrorState error={clear.error} />}

      <Panel title="Resolved messages" bodyClassName="p-0">
        {history.isPending && <Spinner />}
        {history.error && <ErrorState error={history.error} />}
        {history.data?.items.length === 0 && (
          <EmptyState title="Nothing resolved yet" hint="Replayed and discarded messages land here." />
        )}
        <ul className="divide-y divide-border/60">
          {history.data?.items.map((item) => (
            <li key={item.id} className="flex items-stretch gap-3 px-4 py-2.5">
              <StatusEdge status={item.status} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">
                  <span className="font-medium">{item.error.type ?? "Unknown error"}</span>
                  <span className="ml-2 text-muted-foreground">{item.error.message}</span>
                </p>
                <p className="truncate font-mono text-xs text-muted-foreground">
                  {item.sourceTopic} · {item.kafkaId ?? "—"}
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{item.resolvedBy ?? "—"}</span>
                <span>{formatTs(item.resolvedAt)}</span>
                <StatusBadge status={item.status} size="sm" />
              </div>
            </li>
          ))}
        </ul>
        {history.data && (
          <Pagination
            page={history.data.page}
            pageSize={history.data.pageSize}
            total={history.data.total}
            onPage={setPage}
          />
        )}
      </Panel>

      {confirming && (
        <ConfirmDialog
          title="Clear history"
          message={`Permanently deletes all ${history.data?.total ?? 0} resolved messages from the pipeline's own dead letter store. NEW messages are untouched, and the audit trail is kept. This cannot be undone.`}
          confirmLabel="Delete permanently"
          confirmWord="CLEAR"
          loading={clear.isPending}
          onClose={() => setConfirming(false)}
          onConfirm={() => clear.mutate()}
        />
      )}
    </div>
  );
}
