"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/client";
import { DISCARD_COUNTDOWN_SECONDS } from "@/components/Modal";
import { Button } from "@/components/ui";

/**
 * One card in the bottom bar stack (see `BottomBarStack`), covering a bulk
 * run's whole life: an undoable countdown before anything is sent, then live
 * progress once it's launched. One component instance across both phases —
 * the caller keeps rendering the same element and just swaps `pending` for
 * `bulkId` once the countdown fires — so there is one card, not a countdown
 * toast that hands off to a separate progress one.
 *
 * Polls until the server says DONE. Per-message results are always
 * reachable — never summarised away, since a bulk that half-succeeded is the
 * normal case — just collapsed behind "Details" by default so the card stays
 * small while it runs.
 */
export function BulkProgressBar({
  bulkId,
  pending,
  onClose,
  onDone,
}: {
  /** `null` while still in the undo countdown — no run has been launched yet. */
  bulkId: string | null;
  /** Present only during the pre-launch countdown; absent once launched. */
  pending?: {
    message: string;
    seconds?: number;
    /** Fires once, when the countdown reaches 0 — the caller launches the run from here. */
    onCommit: () => void;
    onUndo: () => void;
  };
  onClose: () => void;
  /** Fires exactly once, automatically, when the run reaches DONE — not tied to Dismiss. */
  onDone?: () => void;
}) {
  const [showResults, setShowResults] = useState(false);
  const [remaining, setRemaining] = useState(pending?.seconds ?? DISCARD_COUNTDOWN_SECONDS);
  const pendingActive = Boolean(pending);

  // Refs, not deps: the caller passes fresh closures every render, and
  // depending on them directly would restart the countdown / re-fire onDone
  // on every unrelated re-render of the page above this card.
  const commitRef = useRef(pending?.onCommit);
  commitRef.current = pending?.onCommit;
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;
  const doneFired = useRef(false);

  useEffect(() => {
    if (!pendingActive) return;
    if (remaining <= 0) {
      commitRef.current?.();
      return;
    }
    const timer = setTimeout(() => setRemaining((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [pendingActive, remaining]);

  const { data, error } = useQuery({
    queryKey: ["bulk", bulkId],
    queryFn: () => api.bulkStatus(bulkId as string),
    enabled: Boolean(bulkId),
    refetchInterval: (query) => (query.state.data?.state === "DONE" ? false : 700),
  });

  const done = data?.state === "DONE";

  useEffect(() => {
    if (done && !doneFired.current) {
      doneFired.current = true;
      onDoneRef.current?.();
    }
  }, [done]);

  if (pending) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-lg">
        <p className="flex-1 text-sm" role="status" aria-live="polite">
          {pending.message} Sending in {remaining}s.
        </p>
        <Button size="sm" onClick={pending.onUndo}>
          Undo
        </Button>
      </div>
    );
  }

  if (!bulkId) return null;

  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium">
          {data ? `Bulk ${data.action.toLowerCase()}` : "Bulk"}
          {!done && <span className="ml-1.5 font-normal text-muted-foreground">running…</span>}
        </span>
        {error && <span className="text-xs text-destructive">{String(error)}</span>}
        {data && (
          <span className="flex items-center gap-3 text-xs tabular-nums text-muted-foreground">
            <span className="text-success">{data.ok} ok</span>
            {data.failed > 0 && <span className="text-destructive">{data.failed} failed</span>}
            {data.skipped > 0 && <span>{data.skipped} skipped</span>}
            <span>
              {data.ok + data.failed + data.skipped} / {data.total}
            </span>
          </span>
        )}
        {Boolean(data?.results.length) && (
          <Button
            size="sm"
            icon={showResults ? ChevronUp : ChevronDown}
            onClick={() => setShowResults((v) => !v)}
          >
            Details
          </Button>
        )}
        <Button size="sm" icon={X} className="ml-auto" onClick={onClose}>
          {done ? "Dismiss" : "Hide"}
        </Button>
      </div>

      {data && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-brand transition-all"
            style={{
              width: `${data.total ? ((data.ok + data.failed + data.skipped) / data.total) * 100 : 100}%`,
            }}
          />
        </div>
      )}

      {showResults && data && (
        <ul className="scrollbar-thin mt-3 max-h-48 divide-y divide-border/60 overflow-auto text-xs">
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
              <span className="truncate font-mono text-muted-foreground">{result.messageId}</span>
              {result.error && <span className="truncate text-destructive">{result.error}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
