"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/client";
import { formatTs, prettyJson } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";
import { JsonView, PayloadEditor } from "@/components/Json";
import { BottomBarStack, ConfirmDialog, UndoBar } from "@/components/Modal";
import {
  HeadersField,
  RecordKeyField,
  TargetTopicField,
  useRecordOverrides,
} from "@/components/RecordOverrides";
import { Button, ErrorState, Eyebrow, Input, Spinner } from "@/components/ui";

const AUDIT_ACTION_LABEL: Record<AuditEntry["action"], string> = {
  REPLAY: "Replay",
  EDIT_REPLAY: "Edit & replay",
  DISCARD: "Discard",
  UNDISCARD: "Undiscard",
};

/**
 * One message: its coordinates and error, plus whatever an operator can still
 * do with it. A NEW message gets the live replay/discard form — payload/key
 * /headers/target are always live inputs seeded from the record, so an
 * unedited replay is just the case where nothing here got touched before the
 * button was pressed, not a different code path. A resolved (REPLAYED or
 * DISCARDED) message instead gets a read-only value pane and its full audit
 * trail — every action taken on it, with the record-level detail (key,
 * headers, reason, produced offset, payload diff) each one carried — plus,
 * for a DISCARDED message, the one way back: Undiscard.
 *
 * Shared by the Overview slide-over (always NEW) and the History slide-over
 * (always resolved) and the standalone `/messages/[id]` page (either).
 */
export function MessageDetailPanel({ id }: { id: string }) {
  const queryClient = useQueryClient();

  const [discarding, setDiscarding] = useState(false);
  // Set once the discard is confirmed; the actual call waits for UndoBar's
  // countdown, so closing the confirm dialog doesn't mean the discard already ran.
  const [pendingDiscard, setPendingDiscard] = useState(false);
  const [reason, setReason] = useState("");
  const [payloadText, setPayloadText] = useState<string | null>(null);
  // Seeded from the record once it loads (see the effect below), then edited
  // in place — never reset back to "untouched" by a background refetch.
  const [parsed, setParsed] = useState<unknown>(undefined);
  const overrides = useRecordOverrides();

  const message = useQuery({ queryKey: ["message", id], queryFn: () => api.message(id) });

  useEffect(() => {
    if (message.data && parsed === undefined) setParsed(message.data.payload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message.data]);

  const replay = useMutation({
    mutationFn: () => api.replay(id, { payload: parsed, ...overrides.overrides }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["message", id] });
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
  });

  const discard = useMutation({
    mutationFn: () => api.discard(id, { reason: reason || null }),
    onSuccess: () => {
      setPendingDiscard(false);
      void queryClient.invalidateQueries({ queryKey: ["message", id] });
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
  });

  const undiscard = useMutation({
    mutationFn: () => api.undiscard(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["message", id] });
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
      void queryClient.invalidateQueries({ queryKey: ["audit", id] });
    },
  });

  const audit = useQuery({
    queryKey: ["audit", id],
    queryFn: () => api.messageAudit(id),
    enabled: message.data !== undefined && message.data.status !== "NEW",
  });

  if (message.isPending) return <Spinner />;
  if (message.error) return <ErrorState error={message.error} />;
  if (!message.data) return null;

  const doc = message.data;
  const resolved = doc.status !== "NEW";

  return (
    <div className="space-y-5">
      <h1 className="font-display text-lg font-semibold">{doc.error.type ?? "Unknown error"}</h1>

      <div>
        <Eyebrow>Error</Eyebrow>
        <p className="mt-1 text-sm">{doc.error.message ?? "—"}</p>
        {doc.errorStack && (
          <pre className="code-pane scrollbar-thin mt-2 max-h-40 overflow-auto rounded-md p-3 text-xs">
            {doc.errorStack}
          </pre>
        )}
      </div>

      <dl className="grid grid-cols-3 gap-y-1.5 text-sm">
        <dt className="text-muted-foreground">Source topic</dt>
        <dd className="col-span-2 truncate font-mono" title={doc.sourceTopic ?? undefined}>
          {doc.sourceTopic ?? "—"}
        </dd>
        <dt className="text-muted-foreground">Partition</dt>
        <dd className="col-span-2 font-mono">{doc.partition ?? "—"}</dd>
        <dt className="text-muted-foreground">Offset</dt>
        <dd className="col-span-2 font-mono">{doc.offset ?? "—"}</dd>
        <dt className="text-muted-foreground">Date</dt>
        <dd className="col-span-2">{formatTs(doc.failedAt)}</dd>
      </dl>

      {replay.error && <ErrorState error={replay.error} />}
      {discard.error && <ErrorState error={discard.error} />}
      {undiscard.error && <ErrorState error={undiscard.error} />}

      {resolved && (
        <div className="space-y-4 border-t border-border/60 pt-4">
          <div>
            <Eyebrow>Value</Eyebrow>
            <div className="mt-1">
              <JsonView value={doc.edited ? doc.editedPayload : doc.payload} />
            </div>
          </div>
          {doc.edited && (
            <div>
              <Eyebrow>Original value</Eyebrow>
              <div className="mt-1">
                <JsonView value={doc.payload} />
              </div>
            </div>
          )}
          <div>
            <Eyebrow>Audit trail</Eyebrow>
            <div className="mt-1">
              {audit.isPending && <Spinner />}
              {audit.error && <ErrorState error={audit.error} />}
              {audit.data?.length === 0 && (
                <p className="text-sm text-muted-foreground">No audit entries.</p>
              )}
              {audit.data && audit.data.length > 0 && (
                <ul className="space-y-3">
                  {audit.data.map((entry) => (
                    <li key={entry.id} className="rounded-md border border-border/60 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                        <span className="font-medium">
                          {AUDIT_ACTION_LABEL[entry.action]}
                          {entry.result === "FAILED" && (
                            <span className="ml-2 text-destructive">failed</span>
                          )}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {entry.actor} · {formatTs(entry.at)}
                        </span>
                      </div>
                      {entry.error && <p className="mt-1 text-xs text-destructive">{entry.error}</p>}
                      {Object.keys(entry.detail).length > 0 && (
                        <div className="mt-2">
                          <JsonView value={entry.detail} />
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {!resolved && (
        <div className="space-y-4 border-t border-border/60 pt-4">
          <TargetTopicField
            state={overrides}
            placeholder={doc.sourceTopic ?? "target topic"}
            hint="Left empty, the message goes back to the topic it failed on."
          />

          <RecordKeyField state={overrides} />

          <div>
            <Eyebrow>Value</Eyebrow>
            <div className="mt-1">
              <PayloadEditor
                value={payloadText ?? prettyJson(doc.payload)}
                rows={10}
                onChange={(text, value) => {
                  setPayloadText(text);
                  setParsed(value);
                }}
              />
            </div>
          </div>

          <HeadersField state={overrides} />
        </div>
      )}

      {!resolved && (
        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-4">
          <Button
            variant="brand"
            icon={Send}
            loading={replay.isPending}
            disabled={parsed === undefined || !overrides.valid}
            onClick={() => replay.mutate()}
          >
            Replay
          </Button>
          <Button variant="danger" icon={Archive} onClick={() => setDiscarding(true)}>
            Discard
          </Button>
        </div>
      )}

      {doc.status === "DISCARDED" && (
        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-4">
          <Button
            variant="brand"
            icon={ArchiveRestore}
            loading={undiscard.isPending}
            onClick={() => undiscard.mutate()}
          >
            Undiscard
          </Button>
        </div>
      )}

      {discarding && (
        <ConfirmDialog
          title="Discard this message"
          message="Marks it DISCARDED and records the reason. The document survives — nothing is deleted."
          confirmLabel="Discard"
          onClose={() => setDiscarding(false)}
          onConfirm={() => {
            setDiscarding(false);
            setPendingDiscard(true);
          }}
        >
          <Input
            className="mt-3 w-full"
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </ConfirmDialog>
      )}

      {pendingDiscard && (
        <BottomBarStack>
          <UndoBar
            message="Discarding this message."
            onUndo={() => setPendingDiscard(false)}
            onCommit={() => discard.mutate()}
          />
        </BottomBarStack>
      )}
    </div>
  );
}
