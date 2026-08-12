"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/client";
import { Modal } from "@/components/Modal";
import { Button, Spinner } from "@/components/ui";

/**
 * Live progress for one bulk run.
 *
 * Polls until the server says DONE. Per-message results are always shown, never
 * summarised away: a bulk that half-succeeded is the normal case (some targets
 * were resolved by someone else, some produces failed), and silent partial
 * failure is the bug this screen exists to prevent.
 */
export function BulkProgressModal({
  bulkId,
  onClose,
  onDone,
}: {
  bulkId: string;
  onClose: () => void;
  onDone?: () => void;
}) {
  const { data, error } = useQuery({
    queryKey: ["bulk", bulkId],
    queryFn: () => api.bulkStatus(bulkId),
    refetchInterval: (query) => (query.state.data?.state === "DONE" ? false : 700),
  });

  const done = data?.state === "DONE";

  return (
    <Modal
      title={data ? `Bulk ${data.action.toLowerCase()}` : "Bulk"}
      wide
      onClose={() => {
        onClose();
        if (done) onDone?.();
      }}
      footer={
        <Button
          variant={done ? "primary" : "ghost"}
          onClick={() => {
            onClose();
            if (done) onDone?.();
          }}
        >
          {done ? "Done" : "Run in background"}
        </Button>
      }
    >
      {error && <p className="text-sm text-destructive">{String(error)}</p>}
      {!data && <Spinner label="Starting" />}
      {data && (
        <>
          <div className="mb-3 flex items-center gap-4 text-sm tabular-nums">
            <span className="text-success">{data.ok} ok</span>
            <span className="text-destructive">{data.failed} failed</span>
            <span className="text-muted-foreground">{data.skipped} skipped</span>
            <span className="ml-auto text-muted-foreground">
              {data.ok + data.failed + data.skipped} / {data.total}
            </span>
          </div>

          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-brand transition-all"
              style={{
                width: `${data.total ? ((data.ok + data.failed + data.skipped) / data.total) * 100 : 100}%`,
              }}
            />
          </div>

          <ul className="scrollbar-thin mt-4 max-h-72 divide-y divide-border/60 overflow-auto text-xs">
            {data.results.map((result) => (
              <li key={result.messageId} className="flex items-center gap-2 py-1.5">
                <span
                  className={
                    result.outcome === "ok"
                      ? "text-success"
                      : result.outcome === "skipped"
                        ? "text-muted-foreground"
                        : "text-destructive"
                  }
                >
                  {result.outcome}
                </span>
                <span className="font-mono text-muted-foreground">{result.messageId}</span>
                {result.error && <span className="truncate text-destructive">{result.error}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </Modal>
  );
}
