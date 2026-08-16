"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ChevronLeft, ChevronRight, Pencil, Send } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/client";
import type { ReplayInput } from "@/lib/types";
import { formatTs, payloadId, prettyJson } from "@/lib/format";
import { JsonView, PayloadEditor } from "@/components/Json";
import { ConfirmDialog, DISCARD_COUNTDOWN_SECONDS, Modal } from "@/components/Modal";
import { RecordOverridesFields, useRecordOverrides } from "@/components/RecordOverrides";
import {
  Button,
  Chip,
  ErrorState,
  Eyebrow,
  Input,
  Panel,
  Spinner,
  StatusBadge,
} from "@/components/ui";

/**
 * One message: everything recorded about the failure, and the three actions.
 *
 * Prev/next walk the group the operator arrived from, which is what turns this
 * from a leaf into a serial review loop — decide, advance, decide.
 */
export default function MessagePage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const fingerprint = search.get("fingerprint");
  const status = search.get("status");

  const [editing, setEditing] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [reason, setReason] = useState("");
  const [payloadText, setPayloadText] = useState<string | null>(null);
  const [parsed, setParsed] = useState<unknown>(undefined);
  // Target topic, key and headers all live in the edit modal — the same three
  // fields the bulk form offers, described the same way.
  const overrides = useRecordOverrides();

  const message = useQuery({ queryKey: ["message", id], queryFn: () => api.message(id) });
  const audit = useQuery({ queryKey: ["audit", id], queryFn: () => api.messageAudit(id) });
  const neighbours = useQuery({
    queryKey: ["neighbours", id, fingerprint, status],
    queryFn: () => api.neighbours(id, { fingerprint, status }),
    enabled: Boolean(fingerprint),
  });

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["message", id] });
    void queryClient.invalidateQueries({ queryKey: ["audit", id] });
  }

  const replay = useMutation({
    mutationFn: (input: ReplayInput) => api.replay(id, input),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });

  const discard = useMutation({
    mutationFn: () => api.discard(id, { reason: reason || null }),
    onSuccess: () => {
      setDiscarding(false);
      refresh();
    },
  });

  if (message.isPending) return <Spinner />;
  if (message.error) return <ErrorState error={message.error} />;
  if (!message.data) return null;

  const doc = message.data;
  const docId = payloadId(doc.payload);
  const resolved = doc.status !== "NEW";
  const groupHref = fingerprint ? `/groups/${encodeURIComponent(fingerprint)}` : "/";
  const suffix = `?${fingerprint ? `fingerprint=${encodeURIComponent(fingerprint)}` : ""}${
    status ? `&status=${status}` : ""
  }`;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link
          href={groupHref}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          {fingerprint ? "Group" : "Overview"}
        </Link>
        {fingerprint && (
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              icon={ChevronLeft}
              disabled={!neighbours.data?.prev}
              onClick={() => router.push(`/messages/${neighbours.data?.prev}${suffix}`)}
            >
              Prev
            </Button>
            <Button
              size="sm"
              disabled={!neighbours.data?.next}
              onClick={() => router.push(`/messages/${neighbours.data?.next}${suffix}`)}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {/* Two identities, and the one an operator recognizes leads: the payload's
          own id. The Mongo `_id` is what the API keys on — labelled, because two
          bare hex-ish strings side by side read as one thing said twice. The
          record's own coordinates are `partition` / `offset` in the Coordinates
          panel; the header does not repeat them. */}
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={doc.status} />
        <h1 className="font-display text-xl font-semibold">{doc.error.type ?? "Unknown error"}</h1>
        {docId && (
          <Chip mono title="the payload's own id field">
            id {docId}
          </Chip>
        )}
        <Chip mono title="Mongo _id — the identity every API call uses">
          doc {doc.id}
        </Chip>
        <span className="text-xs text-muted-foreground">failed {formatTs(doc.failedAt)}</span>
      </div>

      {!resolved && (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="brand"
            icon={Send}
            loading={replay.isPending && !editing}
            onClick={() => replay.mutate({})}
          >
            Replay to {doc.sourceTopic}
          </Button>
          <Button icon={Pencil} onClick={() => setEditing(true)}>
            Edit &amp; replay
          </Button>
          <Button variant="danger" icon={Archive} onClick={() => setDiscarding(true)}>
            Discard
          </Button>
        </div>
      )}

      {replay.error && <ErrorState error={replay.error} />}
      {discard.error && <ErrorState error={discard.error} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Payload">
          <JsonView value={doc.payload} />
          {doc.edited && (
            <div className="mt-3">
              {/* The service's own record is never overwritten; the edit lives
                  beside it, so the document still shows what actually failed. */}
              <Eyebrow>Replayed with this edit instead</Eyebrow>
              <JsonView value={doc.editedPayload} className="mt-1" />
            </div>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="Error">
            <p className="text-sm">{doc.error.message ?? "—"}</p>
            {doc.error.normalized && (
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                {doc.error.normalized}
              </p>
            )}
            {doc.errorStack && (
              <pre className="code-pane scrollbar-thin mt-3 max-h-64 overflow-auto rounded-md p-3 text-xs">
                {doc.errorStack}
              </pre>
            )}
          </Panel>

          <Panel title="Coordinates" bodyClassName="p-4 text-sm">
            <dl className="grid grid-cols-3 gap-y-2">
              <dt className="text-muted-foreground">Source topic</dt>
              <dd className="col-span-2 font-mono">{doc.sourceTopic ?? "—"}</dd>
              <dt className="text-muted-foreground">Partition</dt>
              <dd className="col-span-2 font-mono">{doc.partition ?? "—"}</dd>
              <dt className="text-muted-foreground">Offset</dt>
              <dd className="col-span-2 font-mono">{doc.offset ?? "—"}</dd>
              <dt className="text-muted-foreground">Fingerprint</dt>
              <dd className="col-span-2 truncate font-mono text-xs">{doc.fingerprint ?? "—"}</dd>
            </dl>
          </Panel>

          <Panel title="Audit" bodyClassName="p-0">
            {audit.data?.length ? (
              <ul className="divide-y divide-border/60 text-xs">
                {audit.data.map((entry) => (
                  <li key={entry.id} className="flex items-center gap-2 px-4 py-2">
                    <span
                      className={entry.result === "OK" ? "text-success" : "text-destructive"}
                    >
                      {entry.action}
                    </span>
                    <span className="text-muted-foreground">{entry.actor}</span>
                    <span className="ml-auto text-muted-foreground">{formatTs(entry.at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-3 text-xs text-muted-foreground">No actions yet.</p>
            )}
          </Panel>
        </div>
      </div>

      {editing && (
        <Modal
          title="Edit & replay"
          wide
          onClose={() => setEditing(false)}
          footer={
            <>
              <Button onClick={() => setEditing(false)}>Cancel</Button>
              <Button
                variant="brand"
                icon={Send}
                loading={replay.isPending}
                disabled={parsed === undefined || !overrides.valid}
                onClick={() => replay.mutate({ payload: parsed, ...overrides.overrides })}
              >
                Replay edited
              </Button>
            </>
          }
        >
          <div className="space-y-4">
            <div>
              <Eyebrow>Payload</Eyebrow>
              <div className="mt-1">
                <PayloadEditor
                  value={payloadText ?? prettyJson(doc.payload)}
                  onChange={(text, value) => {
                    setPayloadText(text);
                    setParsed(value);
                  }}
                />
              </div>
            </div>

            <RecordOverridesFields
              state={overrides}
              topicPlaceholder={doc.sourceTopic ?? "target topic"}
              topicHint="Left empty, the message goes back to the topic it failed on."
            />
          </div>
        </Modal>
      )}

      {discarding && (
        <ConfirmDialog
          title="Discard this message"
          message="Marks it DISCARDED and records the reason. The document survives — nothing is deleted."
          confirmLabel="Discard"
          countdown={DISCARD_COUNTDOWN_SECONDS}
          loading={discard.isPending}
          onClose={() => setDiscarding(false)}
          onConfirm={() => discard.mutate()}
        >
          <Input
            className="mt-3 w-full"
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </ConfirmDialog>
      )}
    </div>
  );
}
