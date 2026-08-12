"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ChevronLeft, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/client";
import type { BulkEdit } from "@/lib/types";
import { ConfirmDialog, DISCARD_COUNTDOWN_SECONDS } from "@/components/Modal";
import { MessageList } from "@/components/MessageList";
import { BulkEditModal } from "@/components/bulk/BulkEditModal";
import { BulkProgressModal } from "@/components/bulk/BulkProgressModal";
import { useBulk } from "@/components/bulk/useBulk";
import { Button, ErrorState, Eyebrow, Pagination, Panel, Segmented } from "@/components/ui";

/**
 * One error group: every message that hashed to this fingerprint.
 *
 * The key resolves against either namespace — a topic-scoped `fp:` (arrived from
 * a topic screen, so the group lives in one topic) or a cross-topic `efp:`
 * (arrived from the home "by error" lens, so bulk here spans topics).
 */
export default function GroupPage() {
  const params = useParams<{ fingerprint: string }>();
  const fingerprint = decodeURIComponent(params.fingerprint);

  const [status, setStatus] = useState<string | null>("NEW");
  const [page, setPage] = useState(1);
  const [editOpen, setEditOpen] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const bulk = useBulk();

  // Separate from the message page: the header describes the group, so it must
  // not move when the operator flips the status filter or pages through.
  const group = useQuery({
    queryKey: ["group", fingerprint],
    queryFn: () => api.group(fingerprint),
  });

  const messages = useQuery({
    queryKey: ["group-messages", fingerprint, status, page],
    queryFn: () => api.groupMessages(fingerprint, { status, page }),
  });

  const target = { fingerprint };

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Overview
        </Link>
        <div className="mt-1 flex items-end justify-between">
          <div className="min-w-0">
            <Eyebrow>Error group</Eyebrow>
            {/* The exception class leads, the normalized message sits under it
                and the fingerprint drops to a caption — same ordering the group
                rows use, so arriving here is a zoom rather than a change of
                subject. The hash is still on screen because it is what an
                operator pastes into a ticket, just not what identifies the
                group to a human. While the summary loads, the key stands in:
                a blank headline would read as "no such group". */}
            <h1 className="truncate text-lg font-semibold tracking-tight">
              {group.data ? (group.data.errorType ?? "Unknown error") : fingerprint}
            </h1>
            {group.data?.messageSample && (
              <p className="truncate font-mono text-sm text-muted-foreground">
                {group.data.messageSample}
              </p>
            )}
            {group.data && (
              <p className="truncate font-mono text-xs text-muted-foreground/70">{fingerprint}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              value={status ?? "ALL"}
              onChange={(v) => {
                setStatus(v === "ALL" ? null : v);
                setPage(1);
              }}
              options={[
                ["NEW", "New"],
                ["ALL", "All"],
              ]}
            />
            <Button size="sm" variant="brand" icon={Send} onClick={() => setEditOpen(true)}>
              Replay all NEW
            </Button>
            <Button size="sm" variant="danger" icon={Archive} onClick={() => setDiscardOpen(true)}>
              Discard all NEW
            </Button>
          </div>
        </div>
      </div>

      {bulk.error && <ErrorState error={bulk.error} />}

      <Panel title="Messages" bodyClassName="p-0">
        <MessageList
          items={messages.data?.items}
          isPending={messages.isPending}
          // Carry the group + filter so the message screen can offer prev/next
          // through exactly the list the operator is looking at.
          href={(m) =>
            `/messages/${m.id}?fingerprint=${encodeURIComponent(fingerprint)}${
              status ? `&status=${status}` : ""
            }`
          }
        />
        {messages.data && (
          <Pagination
            page={messages.data.page}
            pageSize={messages.data.pageSize}
            total={messages.data.total}
            onPage={setPage}
          />
        )}
      </Panel>

      {editOpen && (
        <BulkEditModal
          target={target}
          onClose={() => setEditOpen(false)}
          onSubmit={(edit: BulkEdit | null) => {
            void bulk.replay(target, edit);
            setEditOpen(false);
          }}
        />
      )}

      {discardOpen && (
        <ConfirmDialog
          title="Discard this error group"
          message="Every NEW message in the group is marked DISCARDED. Soft delete — the documents survive and each one is audited."
          confirmLabel="Discard"
          countdown={DISCARD_COUNTDOWN_SECONDS}
          onClose={() => setDiscardOpen(false)}
          onConfirm={() => {
            void bulk.discard(target);
            setDiscardOpen(false);
          }}
        />
      )}

      {bulk.bulkId && (
        <BulkProgressModal bulkId={bulk.bulkId} onClose={bulk.close} onDone={bulk.finished} />
      )}
    </div>
  );
}
