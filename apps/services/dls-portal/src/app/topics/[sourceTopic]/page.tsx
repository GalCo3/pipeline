"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ChevronLeft, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/client";
import { serviceOf } from "@/lib/format";
import type { BulkEdit, BulkTarget } from "@/lib/types";
import { ConfirmDialog, DISCARD_COUNTDOWN_SECONDS } from "@/components/Modal";
import { GroupRow } from "@/components/GroupRow";
import { MessageList } from "@/components/MessageList";
import { BulkEditModal } from "@/components/bulk/BulkEditModal";
import { BulkProgressModal } from "@/components/bulk/BulkProgressModal";
import { useBulk } from "@/components/bulk/useBulk";
import { Button, ErrorState, Eyebrow, Pagination, Panel, Segmented, Spinner } from "@/components/ui";

/**
 * One topic: its error groups, or a flat list of its messages.
 *
 * The status filter defaults to NEW — the operator's question on arrival is
 * "what still needs a decision", and resolved messages live on the History
 * screen. Bulk actions live here because this is the only screen that can name a
 * whole group or topic as a target.
 */
export default function TopicPage() {
  const params = useParams<{ sourceTopic: string }>();
  const sourceTopic = decodeURIComponent(params.sourceTopic);

  const [view, setView] = useState<"groups" | "messages">("groups");
  const [status, setStatus] = useState<string | null>("NEW");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editTarget, setEditTarget] = useState<BulkTarget | null>(null);
  const [discardTarget, setDiscardTarget] = useState<BulkTarget | null>(null);

  const bulk = useBulk();

  const groups = useQuery({
    queryKey: ["topic-groups", sourceTopic],
    queryFn: () => api.topicGroups(sourceTopic),
    enabled: view === "groups",
  });

  const messages = useQuery({
    queryKey: ["messages", sourceTopic, status, page],
    queryFn: () => api.messages({ sourceTopic, status, page }),
    enabled: view === "messages",
  });

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
          <div>
            <Eyebrow>{serviceOf(sourceTopic)}</Eyebrow>
            <h1 className="font-mono text-xl font-semibold tracking-tight">{sourceTopic}</h1>
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              value={view}
              onChange={(v) => {
                setView(v);
                setSelected(new Set());
              }}
              options={[
                ["groups", "Grouped"],
                ["messages", "Flat"],
              ]}
            />
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
          </div>
        </div>
      </div>

      {bulk.error && <ErrorState error={bulk.error} />}

      {view === "groups" ? (
        <Panel title="Error groups" bodyClassName="p-0">
          {groups.isPending && <Spinner />}
          {groups.error && <ErrorState error={groups.error} />}
          <ul className="divide-y divide-border/60">
            {groups.data?.map((group) => (
              <GroupRow
                key={group.fingerprint}
                group={group}
                href={`/groups/${group.fingerprint}`}
                actions={
                  // Per-group row actions: the fingerprint is a target on its
                  // own, so a whole error can be cleared without selecting its
                  // messages one by one.
                  <span className="flex shrink-0 items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="brand"
                      icon={Send}
                      onClick={() => setEditTarget({ fingerprint: group.fingerprint })}
                    >
                      Replay
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon={Archive}
                      onClick={() => setDiscardTarget({ fingerprint: group.fingerprint })}
                    >
                      Discard
                    </Button>
                  </span>
                }
              />
            ))}
          </ul>
        </Panel>
      ) : (
        <Panel
          title="Messages"
          bodyClassName="p-0"
          action={
            <Button
              size="sm"
              onClick={() => setEditTarget({ sourceTopic })}
              icon={Send}
              variant="brand"
            >
              Replay all NEW
            </Button>
          }
        >
          <MessageList
            items={messages.data?.items}
            isPending={messages.isPending}
            href={(m) => `/messages/${m.id}?topic=${encodeURIComponent(sourceTopic)}`}
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
      )}

      {/* Selection bar — fixed, so the actions stay reachable however far the
          operator has scrolled through a long topic. */}
      {selection && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
            <span className="text-sm tabular-nums">{selected.size} selected</span>
            <Button size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
            <span className="ml-auto flex gap-2">
              <Button size="sm" variant="brand" icon={Send} onClick={() => setEditTarget(selection)}>
                Replay
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
          message="Every NEW message in this target is marked DISCARDED. The documents survive — this is a soft delete — and each one is audited."
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
