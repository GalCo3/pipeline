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

/** Grace period on discard — the one resolution the UI offers no way back from. */
export const DISCARD_COUNTDOWN_SECONDS = 5;

/**
 * Destructive confirmation. `confirmWord` turns it into a type-to-confirm
 * dialog — used by Clear history, which is the one path that deletes data the
 * pipeline wrote.
 *
 * `countdown` adds a grace period *after* the operator commits: the dialog
 * counts down out loud and only then fires, so a mis-aimed discard — the action
 * with no undo in the UI — can still be taken back. Any exit (Cancel, Escape,
 * the backdrop) during the count aborts it, because the action has not run yet.
 */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  confirmWord,
  countdown,
  onConfirm,
  onClose,
  loading,
  children,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  confirmWord?: string;
  countdown?: number;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const armed = !confirmWord || typed.trim().toUpperCase() === confirmWord.toUpperCase();

  // null = not counting. Committing sets it to `countdown` and a tick per
  // second walks it to zero, where the effect fires the action once.
  const [remaining, setRemaining] = useState<number | null>(null);
  const counting = remaining !== null;

  // Held in a ref: call sites pass an inline closure, and depending on its
  // identity would restart the tick on every parent render.
  const confirmRef = useRef(onConfirm);
  confirmRef.current = onConfirm;

  useEffect(() => {
    if (remaining === null) return;
    if (remaining <= 0) {
      setRemaining(null);
      confirmRef.current();
      return;
    }
    const timer = setTimeout(() => setRemaining((n) => (n === null ? null : n - 1)), 1000);
    return () => clearTimeout(timer);
  }, [remaining]);

  const commit = () => (countdown ? setRemaining(countdown) : onConfirm());

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button onClick={counting ? () => setRemaining(null) : onClose}>Cancel</Button>
          <Button
            variant="destructive"
            loading={loading}
            disabled={!armed || counting}
            onClick={commit}
          >
            {counting ? `${confirmLabel} in ${remaining}s` : confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted-foreground">{message}</p>
      {children}
      {counting && (
        <p className="mt-4 text-sm font-medium text-destructive" role="status" aria-live="polite">
          Sending in {remaining}s. Nothing has happened yet — Cancel stops it.
        </p>
      )}
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
