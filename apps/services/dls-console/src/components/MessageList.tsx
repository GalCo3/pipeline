"use client";

import Link from "next/link";

import { relAge } from "@/lib/format";
import type { MessageSummary } from "@/lib/types";
import { EmptyState, Spinner, StatusBadge, StatusEdge } from "@/components/ui";

/**
 * Flat message list, optionally selectable for bulk actions.
 *
 * Two identities show per row and only one is a key: `kafkaId`
 * (`partition:offset`) is what an operator pastes into Kafbat to find the
 * original record, while the Mongo `_id` behind the link is the identity every
 * API call uses. Never key on `kafkaId` — it repeats across topics.
 */
export function MessageList({
  items,
  isPending,
  href,
  selected,
  onToggle,
}: {
  items: MessageSummary[] | undefined;
  isPending?: boolean;
  href: (message: MessageSummary) => string;
  selected?: Set<string>;
  onToggle?: (id: string, checked: boolean) => void;
}) {
  if (isPending) return <Spinner />;
  if (!items?.length) return <EmptyState title="No messages match this filter" />;

  return (
    <ul className="divide-y divide-border/60">
      {items.map((message) => (
        <li key={message.id} className="flex items-stretch gap-3 px-4 py-2.5 hover:bg-accent/50">
          <StatusEdge status={message.status} />
          {onToggle && (
            <input
              type="checkbox"
              checked={Boolean(selected?.has(message.id))}
              onChange={(e) => onToggle(message.id, e.target.checked)}
              aria-label="Select message"
              className="h-4 w-4 self-center accent-[hsl(var(--brand))]"
            />
          )}
          <Link href={href(message)} className="flex min-w-0 flex-1 items-center gap-4">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">
                <span className="font-medium">{message.error.type ?? "Unknown error"}</span>
                <span className="ml-2 text-muted-foreground">{message.error.message}</span>
              </p>
              <p className="truncate font-mono text-xs text-muted-foreground">
                {message.sourceTopic} · {message.kafkaId ?? "—"}
              </p>
            </div>
            <StatusBadge status={message.status} size="sm" />
            <span className="w-12 text-right text-xs text-muted-foreground">
              {relAge(message.failedAt)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
