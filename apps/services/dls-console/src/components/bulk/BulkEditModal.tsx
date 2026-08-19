"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/client";
import type { BulkEdit, BulkTarget } from "@/lib/types";
import { Modal } from "@/components/Modal";
import { FieldsEditor } from "@/components/Fields";
import { RecordOverridesFields, useRecordOverrides } from "@/components/RecordOverrides";
import { Button, Eyebrow, Spinner } from "@/components/ui";

/**
 * Bulk edit & replay — shared values only.
 *
 * The server deep-compares the target's NEW payloads and returns the top-level
 * keys identical across all of them, and only those are offered as fields. That
 * restraint is the point: one form applied to N messages can only safely set a
 * value that was already the same in all of them, and the alternative (edit a
 * key that varies) would overwrite real per-message data. The keys that differ
 * are simply absent — a message-by-message fact has no single value to show
 * here, and listing them told the operator nothing they could act on.
 *
 * Past the server's inspection cap it answers `tooMany`, and the payload form
 * degrades to a plain replay-all rather than guessing. The record-level fields
 * (target topic, headers) are unaffected either way — they are supplied rather
 * than derived, so nothing has to be compared to offer them.
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

  // `touched` rather than a value comparison: an operator who only wanted a
  // redirect must not have every payload rewritten with the shared values.
  const [touched, setTouched] = useState(false);
  const [fields, setFields] = useState<Record<string, unknown> | undefined>(undefined);
  const overrides = useRecordOverrides();

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
            disabled={!overrides.valid || (canEdit && touched && fields === undefined)}
            onClick={() =>
              onSubmit({
                // Past the comparison cap there is no payload form at all, but
                // the record-level overrides still apply.
                payload: canEdit && touched ? (fields ?? null) : null,
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
            <div>
              <Eyebrow>Shared payload fields</Eyebrow>
              <div className="mt-1">
                <FieldsEditor
                  initial={data.payload}
                  emptyHint="No values are shared across every message."
                  onChange={(value, error) => {
                    setTouched(true);
                    setFields(error ? undefined : value);
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Applied as a shallow merge over each message&apos;s own payload — nested objects
                are replaced whole, and new fields may be added.
              </p>
            </div>
          )}

          <RecordOverridesFields
            state={overrides}
            showKey={false}
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
