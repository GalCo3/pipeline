"use client";

import { ArrowRight, Network, Repeat } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { relAge } from "@/lib/format";
import type { GroupSummary } from "@/lib/types";
import { Chip, CountsBar } from "@/components/ui";

/**
 * One error group.
 *
 * The exception class leads at body size and the normalized message sits under
 * it in mono — an operator scanning this list is matching on the class first and
 * reading the message only once something catches. The sample shown is the
 * *normalized* error, not a raw one: a group whose members differ only by an
 * interpolated id would otherwise display one arbitrary id as if it
 * characterized the whole group.
 *
 * The numeric columns are fixed-width and tabular so occurrences, spread and
 * status counts line up down the list into readable columns instead of drifting
 * with the length of the text beside them.
 */
export function GroupRow({
  group,
  href,
  actions,
  selected,
  onSelect,
}: {
  group: GroupSummary;
  href: string;
  actions?: ReactNode;
  selected?: boolean;
  onSelect?: (checked: boolean) => void;
}) {
  return (
    // gap-5 throughout, matching the overview's ColumnHeader — the header only
    // lines up with the row while the two use the same rhythm.
    <li className="flex items-center gap-5 px-5 py-4 transition hover:bg-accent/50">
      {onSelect && (
        <input
          type="checkbox"
          checked={Boolean(selected)}
          onChange={(e) => onSelect(e.target.checked)}
          aria-label="Select group"
          className="h-4 w-4 accent-[hsl(var(--brand))]"
        />
      )}
      <Link
        href={href}
        className="flex min-w-0 flex-1 items-center gap-5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-semibold leading-6 tracking-tight">
            {group.errorType ?? "Unknown error"}
          </p>
          <p className="truncate font-mono text-sm leading-6 text-muted-foreground">
            {group.messageSample ?? "—"}
          </p>
        </div>
        <Chip
          icon={Repeat}
          title="occurrences — one DLS document per failure"
          className="w-14 justify-center"
        >
          {group.count}
        </Chip>
        {/* The slot is always there so the column stays straight down the list;
            only a genuinely cross-cutting error fills it — a "1" here would be
            noise on every row of a topic-scoped list. */}
        <span className="w-14 shrink-0 text-center">
          {group.topicCount !== undefined && group.topicCount > 1 && (
            <Chip icon={Network} tone="info" title="source topics this error spans">
              {group.topicCount}
            </Chip>
          )}
        </span>
        <CountsBar counts={group.counts} />
        <span className="hidden w-14 shrink-0 text-right text-sm tabular-nums text-muted-foreground sm:block">
          {relAge(group.lastSeenAt)}
        </span>
      </Link>
      {actions}
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </li>
  );
}
