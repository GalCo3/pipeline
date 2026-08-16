"use client";

import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/client";
import { prettyJson } from "@/lib/format";
import type { BulkEdit, BulkTarget } from "@/lib/types";
import { Modal } from "@/components/Modal";
import { PayloadEditor } from "@/components/Json";
import { RecordOverridesFields, useRecordOverrides } from "@/components/RecordOverrides";
import { Button, Eyebrow, Spinner } from "@/components/ui";

/**
 * Bulk edit & replay — shared values only.
 *
 * The server deep-compares the target's NEW payloads and returns the top-level
 * keys identical across all of them; anything that differs is listed as locked
 * rather than silently editable. That restraint is the point: one form applied
 * to N messages can only safely set a value that was already the same in all of
 * them, and the alternative (edit a key that varies) would overwrite real
 * per-message data.
 *
 * Past the server's inspection cap it answers `tooMany`, and the payload form
 * degrades to a plain replay-all rather than guessing. The record-level fields
 * (target topic, key, headers) are unaffected either way — they are supplied
 * rather than derived, so nothing has to be compared to offer them.
 */
export function BulkEditModal({
  target,
  onClose,
  onSubmit,
}: {
  target: BulkTarget;
  onClose: () => void;
  onSubmit: (edit: BulkEdit | null) => void;
}) {
  const { data, isPending, error } = useQuery({
    queryKey: ["bulk-shared", target],
    queryFn: () => api.bulkShared(target),
  });

  const [text, setText] = useState<string | null>(null);
  const [parsed, setParsed] = useState<Record<string, unknown> | undefined>(undefined);
  const overrides = useRecordOverrides();

  const shared = data?.payload ?? {};
  const value = text ?? prettyJson(shared);
  const canEdit = Boolean(data && !data.tooMany && data.eligible > 0);

  return (
    <Modal
      title="Bulk edit & replay"
      wide
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="brand"
            disabled={!overrides.valid || (canEdit && text !== null && parsed === undefined)}
            onClick={() =>
              onSubmit({
                // Untouched editor → no payload edit at all, so an operator who
                // only wanted a redirect doesn't rewrite every payload with the
                // shared values. Past the comparison cap there is no payload form
                // at all, but the record-level overrides still apply.
                payload: canEdit && text !== null ? (parsed ?? null) : null,
                ...overrides.overrides,
              })
            }
          >
            Replay {data?.total ?? 0} message{data?.total === 1 ? "" : "s"}
          </Button>
        </>
      }
    >
      {isPending && <Spinner label="Comparing payloads" />}
      {error && <p className="text-sm text-destructive">{String(error)}</p>}

      {data && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {data.total} NEW message{data.total === 1 ? "" : "s"} in this target.
            {data.tooMany
              ? " Too many to compare payloads — this will replay them unedited."
              : " Only values identical across every one of them can be edited."}
          </p>

          {canEdit && (
            <>
              <div>
                <Eyebrow>Shared payload keys</Eyebrow>
                <div className="mt-1">
                  <PayloadEditor
                    rows={12}
                    value={value}
                    onChange={(next, parsedValue) => {
                      setText(next);
                      setParsed(
                        parsedValue && typeof parsedValue === "object" && !Array.isArray(parsedValue)
                          ? (parsedValue as Record<string, unknown>)
                          : undefined,
                      );
                    }}
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Applied as a shallow merge over each message&apos;s own payload — nested objects
                  are replaced whole, and new keys may be added.
                </p>
              </div>

              {data.varyingPayloadKeys.length > 0 && (
                <div>
                  <Eyebrow>Varies across messages — not editable</Eyebrow>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {data.varyingPayloadKeys.map((key) => (
                      <span
                        key={key}
                        className="inline-flex items-center gap-1 rounded-sm bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground"
                      >
                        <Lock className="h-3 w-3" />
                        {key}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          <RecordOverridesFields
            state={overrides}
            topicPlaceholder={
              data.targetVaries
                ? "messages replay to their own source topic"
                : (data.targetTopic ?? "")
            }
            topicHint={
              data.targetVaries
                ? "This group spans topics. Left empty, each message goes back to the topic it failed on."
                : "Left empty, every message goes back to the topic it failed on."
            }
          />
        </div>
      )}
    </Modal>
  );
}
