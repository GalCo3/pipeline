"use client";

import { Archive, ArchiveRestore, Search, Send, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/client";
import { fullNum } from "@/lib/format";
import {
  STATUSES,
  type BulkEdit,
  type BulkTarget,
  type MessageFilterModel,
  type MessageSortKey,
} from "@/lib/types";
import { BottomBarStack, ConfirmDialog, Sheet } from "@/components/Modal";
import { MessageDataGrid } from "@/components/MessageDataGrid";
import { MessageDetailPanel } from "@/components/MessageDetailPanel";
import { STATUS_META } from "@/components/status";
import { BulkEditModal } from "@/components/bulk/BulkEditModal";
import { BulkProgressBar } from "@/components/bulk/BulkProgressBar";
import { useBulk } from "@/components/bulk/useBulk";
import { Button, ErrorState, Input, MultiSelect, Spinner } from "@/components/ui";

const EMPTY_FILTER: MessageFilterModel = { items: [] };

/** `?filter=` round-trips as JSON; a malformed or absent value just means "no column filters". */
function parseFilterParam(raw: string | null): MessageFilterModel {
  if (!raw) return EMPTY_FILTER;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && Array.isArray(parsed.items)) return parsed as MessageFilterModel;
  } catch {
    // fall through
  }
  return EMPTY_FILTER;
}

// No real topic, error fingerprint, or message id ever collides with this —
// it marks "the operator explicitly unchecked every box" in a toggle menu's
// URL param, distinct from the param being absent (which means the default,
// every box checked / unfiltered). Reused as the value handed to the API in
// that case too: a filter for a value nothing has is exactly "match none".
const NONE = " none";

/**
 * Backlog — every dead-lettered message, one flat paginated list, one screen,
 * everything else in the query string. There is no separate history screen:
 * `Status` is just another grid column, filterable the same way as every
 * other one, so narrowing to NEW (the actual backlog) or to REPLAYED /
 * DISCARDED (the history) is the same interaction as any other column filter.
 *
 * Filterable by topic, error group and (live, substring) message id.
 * `topic`, `fingerprint`, `id`, `page`, `pageSize` are the state; nothing
 * material lives in a `useState` that isn't reflected in the address bar.
 */
export default function BacklogPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Backlog />
    </Suspense>
  );
}

function Backlog() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const topicParam = searchParams.get("topic");
  const errorParam = searchParams.get("fingerprint");
  const statusParam = searchParams.get("status");
  const idParam = searchParams.get("id");
  const sortBy = (searchParams.get("sortBy") as MessageSortKey | null) ?? "failedAt";
  const sortDir = searchParams.get("sortDir") === "asc" ? "asc" : "desc";
  const page = Math.max(1, Number(searchParams.get("page") ?? 1) || 1);
  const pageSize = Number(searchParams.get("pageSize") ?? 50) || 50;
  const filterModel = parseFilterParam(searchParams.get("filter"));
  // The message the detail slide-over shows, if any — a URL param rather than
  // local state so the panel survives a refresh and is a shareable link, the
  // same way `/messages/[id]` already is for a direct navigation.
  const messageParam = searchParams.get("message");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editTarget, setEditTarget] = useState<BulkTarget | null>(null);
  const [discardTarget, setDiscardTarget] = useState<BulkTarget | null>(null);
  const [discardReason, setDiscardReason] = useState("");
  // Set once the discard is confirmed; drives the one bottom-right card
  // through its whole life — undo countdown, then live progress — until
  // dismissed. The actual `bulk.discard` call waits for the countdown, so
  // confirming the dialog doesn't mean the discard already ran.
  const [discardFlow, setDiscardFlow] = useState<{
    target: BulkTarget;
    reason: string | null;
  } | null>(null);
  // Bumped every time a bulk action (re)starts, and used as `BulkProgressBar`'s
  // `key` below — forces a fresh mount rather than reusing the previous run's
  // instance, whose internal countdown and "have I already called onDone"
  // state would otherwise carry over: a second discard's card would render
  // with `remaining` still at 0 from the first run (skipping the undo grace
  // period entirely) and `onDone` would never fire again (the list would stop
  // auto-refreshing after the very first bulk action of the session).
  const [actionNonce, setActionNonce] = useState(0);
  // Local, uncommitted copy of the `id` param — typing updates this
  // immediately for a responsive input, then a short debounce pushes it into
  // the URL (and triggers the query) so fast typing doesn't fire a request
  // per keystroke. Resynced whenever the URL's own `id` changes out from
  // under it (a shared link, the back button).
  const [idText, setIdText] = useState(idParam ?? "");
  useEffect(() => setIdText(idParam ?? ""), [idParam]);
  const idDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (idDebounce.current) clearTimeout(idDebounce.current);
    },
    [],
  );

  const bulk = useBulk();

  /** Merge into the current query string and navigate — the one place state changes. */
  function updateParams(updates: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    const qs = next.toString();
    router.push(qs ? `/?${qs}` : "/", { scroll: false });
  }

  // Always fetched — these back the topic and error filter menus.
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics });

  // Every toggle menu defaults to "every box checked" rather than "none" — an
  // absent URL param means unfiltered, so the default selection is the full
  // option list. Unchecking every box is still a real, distinct choice
  // ("show nothing"), spelled as the `NONE` marker in both the URL and the
  // API call — no real topic/error is ever named that, so it matches zero
  // documents. `narrowed` turns a selection back into an API filter: null
  // (no filter) for the full set, `[NONE]` for empty, an explicit list
  // otherwise.
  function narrowed(selected: Set<string>, all: string[]): string[] | null {
    if (selected.size === all.length) return null;
    if (selected.size === 0) return [NONE];
    return [...selected];
  }

  function decode(param: string | null, all: string[], fallback: string[] = all): Set<string> {
    if (param === null) return new Set(fallback);
    if (param === NONE) return new Set();
    return new Set(param.split(",").filter(Boolean));
  }

  const topicOptions = topics.data?.map((t) => t.sourceTopic) ?? [];
  const topicFilter = decode(topicParam, topicOptions);
  const topicArray = narrowed(topicFilter, topicOptions);

  // Scoped to a single selected topic when there is exactly one, so the error
  // menu only lists errors that actually occur there.
  const groups = useQuery({
    queryKey: ["groups", topicArray?.length === 1 ? topicArray[0] : null],
    queryFn: () => (topicArray?.length === 1 ? api.topicGroups(topicArray[0]) : api.allGroups()),
  });

  const errorOptions = groups.data?.map((g) => g.fingerprint) ?? [];
  const errorFilter = decode(errorParam, errorOptions);
  const errorArray = narrowed(errorFilter, errorOptions);

  // `middleware.ts` redirects a bare `/` to `?status=NEW`, so by the time this
  // renders the param is always present — "NEW only" is an explicit URL state,
  // not a fallback special-cased here the way it would be for topic/error.
  const statusFilter = decode(statusParam, STATUSES);
  const statusArray = narrowed(statusFilter, STATUSES);

  const messages = useQuery({
    queryKey: [
      "messages",
      topicArray,
      errorArray,
      statusArray,
      idParam,
      filterModel,
      sortBy,
      sortDir,
      page,
      pageSize,
    ],
    queryFn: () =>
      api.messages({
        sourceTopic: topicArray,
        fingerprint: errorArray,
        status: statusArray,
        id: idParam,
        filter: filterModel,
        sortBy,
        sortDir,
        page,
        pageSize,
      }),
  });

  function changeSort(key: MessageSortKey, dir: "asc" | "desc") {
    const isDefault = key === "failedAt" && dir === "desc";
    updateParams({ sortBy: isDefault ? null : key, sortDir: isDefault ? null : dir, page: null });
  }

  function changeFilter(model: MessageFilterModel) {
    updateParams({ filter: model.items.length ? JSON.stringify(model) : null, page: null });
  }

  // Anything narrower than the bare-`/` default (NEW only, no other filters)
  // counts as active. `statusParam` alone can't be compared to `null` the way
  // the others can — see the `status` update below — so it's active whenever
  // it names anything other than plain "NEW".
  const hasActiveFilters = Boolean(
    topicParam || errorParam || idParam || filterModel.items.length || (statusParam && statusParam !== "NEW"),
  );

  function clearAllFilters() {
    updateParams({ topic: null, fingerprint: null, status: null, id: null, filter: null, page: null });
  }

  // Replay/Discard need every checked row to be NEW (the only actionable
  // status); Undiscard needs every checked row to be DISCARDED (the one way
  // back). A selection spanning more than one status — or a row on a page
  // that hasn't loaded — offers neither: status is only known for rows
  // actually on screen.
  const selectedRows = (messages.data?.items ?? []).filter((m) => selected.has(m.id));
  const selectedStatus =
    selected.size > 0 && selectedRows.length === selected.size
      ? new Set(selectedRows.map((m) => m.status))
      : null;
  const selection: BulkTarget | null =
    selectedStatus?.size === 1 && selectedStatus.has("NEW") ? { messageIds: [...selected] } : null;
  const undiscardTarget: BulkTarget | null =
    selectedStatus?.size === 1 && selectedStatus.has("DISCARDED")
      ? { messageIds: [...selected] }
      : null;

  return (
    // Every fixed-position overlay below (Sheet, BottomBarStack, the modals)
    // sits outside this `space-y-5` div rather than as one of its children:
    // that utility adds a top margin to every non-first child via a sibling
    // selector, which doesn't check `position` — a `fixed` overlay inside it
    // would inherit that margin too, shifting it down from the true viewport
    // top (a visible undimmed strip above the panel).
    <>
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-4xl font-semibold tabular-nums tracking-tight">
              {messages.data ? `${fullNum(messages.data.total)} records` : " "}
            </h1>
          </div>
          {selection && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="brand"
                icon={Send}
                onClick={() => setEditTarget(selection)}
              >
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
            </div>
          )}
          {undiscardTarget && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="brand"
                icon={ArchiveRestore}
                onClick={() => {
                  setActionNonce((n) => n + 1);
                  void bulk.undiscard(undiscardTarget);
                  setSelected(new Set());
                }}
              >
                Undiscard
              </Button>
            </div>
          )}
        </div>

        {bulk.error && <ErrorState error={bulk.error} />}

        <div className="flex flex-wrap items-center gap-2">
          <MultiSelect
            label="Filter by topic"
            placeholder="All topics"
            className="w-44"
            options={(topics.data ?? []).map((t) => ({
              value: t.sourceTopic,
              label: t.sourceTopic,
            }))}
            selected={topicFilter}
            onChange={(next) =>
              updateParams({ topic: narrowed(next, topicOptions)?.join(",") ?? null, page: null })
            }
          />

          <MultiSelect
            label="Filter by error"
            placeholder="All errors"
            className="w-44"
            options={(groups.data ?? []).map((g) => ({
              value: g.fingerprint,
              label: g.errorType ?? g.messageSample ?? "Unknown error",
            }))}
            selected={errorFilter}
            onChange={(next) =>
              updateParams({
                fingerprint: narrowed(next, errorOptions)?.join(",") ?? null,
                page: null,
              })
            }
          />

          <MultiSelect
            label="Filter by status"
            placeholder="All statuses"
            className="w-44"
            options={STATUSES.map((status) => ({
              value: status,
              label: STATUS_META[status].label,
              icon: STATUS_META[status].Icon,
            }))}
            selected={statusFilter}
            onChange={(next) =>
              // Never collapse a full selection to an absent param the way
              // `narrowed` does for topic/error: an absent `status` means
              // "NEW only" (see `middleware.ts`), so checking every box back
              // in has to write it out explicitly or the redirect there
              // would immediately undo the click.
              updateParams({ status: next.size === 0 ? NONE : [...next].join(","), page: null })
            }
          />

          <div className="relative flex items-center">
            <Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="id"
              value={idText}
              onChange={(e) => {
                const value = e.target.value;
                setIdText(value);
                if (idDebounce.current) clearTimeout(idDebounce.current);
                idDebounce.current = setTimeout(() => {
                  updateParams({ id: value.trim() || null, page: null });
                }, 300);
              }}
              className="w-64 pl-8 font-mono text-sm"
              aria-label="Filter by message id"
            />
          </div>

          {hasActiveFilters && (
            <Button size="sm" variant="ghost" icon={X} onClick={clearAllFilters}>
              Clear filters
            </Button>
          )}
        </div>

        <MessageDataGrid
          items={messages.data?.items}
          total={messages.data?.total ?? 0}
          isPending={messages.isPending}
          page={page}
          pageSize={pageSize}
          sortBy={sortBy}
          sortDir={sortDir}
          filterModel={filterModel}
          selected={selected}
          onSelectionChange={setSelected}
          onPageChange={(p) => updateParams({ page: p === 1 ? null : String(p) })}
          onPageSizeChange={(size) => updateParams({ pageSize: String(size), page: null })}
          onSortChange={changeSort}
          onFilterChange={changeFilter}
          onOpen={(m) => updateParams({ message: m.id })}
        />
      </div>

      {messageParam && (
        <Sheet
          title={<span className="font-display text-sm font-semibold">Message detail</span>}
          onClose={() => updateParams({ message: null })}
        >
          <MessageDetailPanel key={messageParam} id={messageParam} />
        </Sheet>
      )}

      {/* One card, covering whichever bulk action is live — the discard flow's
          undo countdown through to its finished progress, or a replay's
          progress on its own once discard isn't in play. */}
      {(discardFlow || bulk.bulkId) && (
        <BottomBarStack>
          <BulkProgressBar
            key={actionNonce}
            bulkId={bulk.bulkId}
            pending={
              discardFlow && !bulk.bulkId
                ? {
                    message: "Discarding the selected messages.",
                    onCommit: () => {
                      void bulk.discard(discardFlow.target, discardFlow.reason);
                      setSelected(new Set());
                    },
                    onUndo: () => setDiscardFlow(null),
                  }
                : undefined
            }
            onClose={() => {
              bulk.close();
              setDiscardFlow(null);
            }}
            onDone={bulk.refresh}
          />
        </BottomBarStack>
      )}

      {editTarget && (
        <BulkEditModal
          target={editTarget}
          onClose={() => setEditTarget(null)}
          onSubmit={(edit: BulkEdit | null) => {
            setActionNonce((n) => n + 1);
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
          onClose={() => {
            setDiscardTarget(null);
            setDiscardReason("");
          }}
          onConfirm={() => {
            // A finished run's `bulkId` only clears on Dismiss — if it's
            // still sitting there from an earlier discard, `pending` below
            // would stay false (bulkId set) and this new flow would never
            // start its countdown.
            bulk.close();
            setActionNonce((n) => n + 1);
            setDiscardFlow({ target: discardTarget, reason: discardReason || null });
            setDiscardTarget(null);
            setDiscardReason("");
          }}
        >
          <Input
            className="mt-3 w-full"
            placeholder="Reason (optional)"
            value={discardReason}
            onChange={(e) => setDiscardReason(e.target.value)}
          />
        </ConfirmDialog>
      )}
    </>
  );
}
