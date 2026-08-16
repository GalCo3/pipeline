"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ChevronLeft, Pencil, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/client";
import type { BulkEdit, BulkTarget } from "@/lib/types";
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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Both bulk entry points aim the same modal, so they share one target slot:
  // the whole group, or just the rows the operator ticked.
  const [editTarget, setEditTarget] = useState<BulkTarget | null>(null);
  const [discardTarget, setDiscardTarget] = useState<BulkTarget | null>(null);
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

  const wholeGroup: BulkTarget = { fingerprint };
  const selection: BulkTarget | null = selected.size ? { messageIds: [...selected] } : null;

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
            <Button
              size="sm"
              variant="brand"
              icon={Pencil}
              onClick={() => setEditTarget(wholeGroup)}
            >
              Bulk edit &amp; replay
            </Button>
            <Button
              size="sm"
              variant="danger"
              icon={Archive}
              onClick={() => setDiscardTarget(wholeGroup)}
            >
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
          selected={selected}
          onToggle={(id, checked) =>
            setSelected((prev) => {
              const next = new Set(prev);
              if (checked) next.add(id);
              else next.delete(id);
              return next;
            })
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

      {/* Selection bar — fixed, so the actions stay reachable however far the
          operator has scrolled through a long group. */}
      {selection && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
            <span className="text-sm tabular-nums">{selected.size} selected</span>
            <Button size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
            <span className="ml-auto flex gap-2">
              <Button size="sm" variant="brand" icon={Send} onClick={() => setEditTarget(selection)}>
                Edit &amp; replay
              </Button>
              <Button
                size="sm"
                variant="danger"
                icon={Archive}
                onClick={() => setDiscardTarget(selection)}
              >
                Discard
              </Button>
            </span>
          </div>
        </div>
      )}

      {editTarget && (
        <BulkEditModal
          target={editTarget}
          onClose={() => setEditTarget(null)}
          onSubmit={(edit: BulkEdit | null) => {
            void bulk.replay(editTarget, edit);
            setEditTarget(null);
            setSelected(new Set());
          }}
        />
      )}

      {discardTarget && (
        <ConfirmDialog
          title="Discard messages"
          message="Every NEW message in this target is marked DISCARDED. Soft delete — the documents survive and each one is audited."
          confirmLabel="Discard"
          countdown={DISCARD_COUNTDOWN_SECONDS}
          onClose={() => setDiscardTarget(null)}
          onConfirm={() => {
            void bulk.discard(discardTarget);
            setDiscardTarget(null);
            setSelected(new Set());
          }}
        />
      )}

      {bulk.bulkId && (
        <BulkProgressModal bulkId={bulk.bulkId} onClose={bulk.close} onDone={bulk.finished} />
      )}
    </div>
  );
}
