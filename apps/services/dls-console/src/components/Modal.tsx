"use client";

import { X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button, Input } from "@/components/ui";

/** Centred dialog. Escape closes; the backdrop click does too. */
export function Modal({
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal
        onClick={(e) => e.stopPropagation()}
        className={`flex max-h-[85vh] w-full flex-col rounded-lg border border-border bg-card shadow-lg ${
          wide ? "max-w-3xl" : "max-w-lg"
        }`}
      >
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <h2 className="font-display text-sm font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-auto p-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-border/60 px-4 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}

/**
 * Slide-over panel, anchored to the right edge, full viewport height. Same
 * escape/backdrop-click-to-close contract as `Modal` — it's a dialog, just
 * shaped for content an operator reads alongside the list behind it (the
 * message detail view) instead of content that blocks the whole screen.
 */
export function Sheet({
  title,
  onClose,
  children,
  footer,
  headerExtra,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  /** extra controls in the header, beside the title (e.g. prev/next) */
  headerExtra?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        role="dialog"
        aria-modal
        onClick={(e) => e.stopPropagation()}
        className="settle-in flex h-full w-full max-w-md flex-col border-l border-border bg-background shadow-lg"
      >
        <div className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3">
          <div className="min-w-0 flex-1">{title}</div>
          <div className="flex shrink-0 items-center gap-2">
            {headerExtra}
            <button
              onClick={onClose}
              aria-label="Close"
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="scrollbar-thin flex-1 overflow-auto p-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-border/60 px-5 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}

/**
 * Plain confirmation. `confirmWord` turns it into a type-to-confirm dialog —
 * used by Clear history, the one path that deletes data the pipeline wrote.
 *
 * Discard's own grace period lives outside this dialog now (see `UndoBar`):
 * confirming here fires immediately and closes, so the countdown runs as a
 * dismissible toast instead of a modal that blocks the rest of the screen.
 */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  confirmWord,
  onConfirm,
  onClose,
  loading,
  children,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  confirmWord?: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const armed = !confirmWord || typed.trim().toUpperCase() === confirmWord.toUpperCase();

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="destructive" loading={loading} disabled={!armed} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted-foreground">{message}</p>
      {children}
      {confirmWord && (
        <label className="mt-4 block">
          <span className="text-xs text-muted-foreground">
            Type <span className="font-mono font-semibold text-foreground">{confirmWord}</span> to
            confirm
          </span>
          <Input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="mt-1 w-full font-mono"
          />
        </label>
      )}
    </Modal>
  );
}

/** Grace period before an undoable action actually fires. */
export const DISCARD_COUNTDOWN_SECONDS = 5;

/**
 * Non-blocking undo toast — one bar in the bottom bar stack (see
 * `BottomBarStack`), not self-positioned. Discard is the one resolution the
 * UI offers no way back from, so committing it doesn't fire right away: this
 * bar counts down out loud and only then calls `onCommit`, while the rest of
 * the screen — including starting another action — stays fully usable.
 * `onUndo` cancels it; unmounting the bar (a parent clearing its pending
 * state) has the same effect since the timer lives in this component's own
 * effect.
 */
export function UndoBar({
  message,
  seconds = DISCARD_COUNTDOWN_SECONDS,
  onCommit,
  onUndo,
}: {
  message: string;
  seconds?: number;
  onCommit: () => void;
  onUndo: () => void;
}) {
  const [remaining, setRemaining] = useState(seconds);

  // Held in a ref: call sites pass an inline closure, and depending on its
  // identity would restart the tick on every parent render.
  const commitRef = useRef(onCommit);
  commitRef.current = onCommit;

  useEffect(() => {
    if (remaining <= 0) {
      commitRef.current();
      return;
    }
    const timer = setTimeout(() => setRemaining((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [remaining]);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-lg">
      <p className="flex-1 text-sm" role="status" aria-live="polite">
        {message} Sending in {remaining}s.
      </p>
      <Button size="sm" onClick={onUndo}>
        Undo
      </Button>
    </div>
  );
}

/**
 * The single fixed container every bottom bar renders inside — the selection
 * bar, `UndoBar`, `BulkProgressBar`. Anchored to the bottom-right corner as a
 * stack of narrow toast cards rather than a full-width banner, so an action's
 * feedback doesn't block the rest of the screen while it runs.
 * `column-reverse` means the first child in markup order sits at the bottom
 * edge and each one after it stacks above, so however many are active at once
 * (replay a group, then discard a different selection before its progress
 * card is dismissed — three cards, not a guess about which two can coexist),
 * real layout does the stacking instead of a hand-picked pixel offset that
 * only covers the cases anticipated. List children bottom-most-first.
 */
export function BottomBarStack({ children }: { children: ReactNode }) {
  return (
    <div className="fixed bottom-4 right-4 z-40 flex w-full max-w-sm flex-col-reverse gap-2">
      {children}
    </div>
  );
}
