"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Layers, Radio } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/client";
import { cx, relAge, serviceOf } from "@/lib/format";
import type { Status } from "@/lib/types";
import { GroupRow } from "@/components/GroupRow";
import {
  Card,
  Chip,
  CountsBar,
  EmptyState,
  ErrorState,
  Eyebrow,
  Panel,
  Segmented,
  Spinner,
} from "@/components/ui";
import { STATUS_META } from "@/components/status";

/**
 * Overview — the drill-down's first rung.
 *
 * Two lenses over the same store, because the operator arrives with one of two
 * questions. "By topic" answers *which service is bleeding*; "by error" answers
 * *what is actually broken*, collapsing one bug that hits four topics into one
 * row instead of four.
 *
 * Layout is deliberately three tiers and no more — headline, the four counts,
 * one list. Everything an operator does here is "read the number, open the
 * list", so a second list competing for the same glance was removed rather than
 * re-styled.
 */
export default function OverviewPage() {
  const [lens, setLens] = useState<"topics" | "errors">("topics");

  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics, enabled: lens === "topics" });
  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: api.allGroups,
    enabled: lens === "errors",
  });

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Dead letter store</Eyebrow>
          <h1 className="mt-1 font-display text-4xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1.5 text-base text-muted-foreground">
            Everything the pipeline could not process, grouped so one bug reads as one row.
          </p>
        </div>
        <Segmented
          value={lens}
          onChange={setLens}
          options={[
            ["topics", "By topic"],
            ["errors", "By error"],
          ]}
        />
      </div>

      {stats.data && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat
            label="New"
            value={stats.data.totals.NEW}
            tone="warning"
            hint="waiting on triage"
          />
          <Stat
            label="Replayed"
            value={stats.data.totals.REPLAYED}
            tone="success"
            hint="sent back to their topic"
          />
          <Stat
            label="Discarded"
            value={stats.data.totals.DISCARDED}
            tone="muted"
            hint="closed without replay"
          />
          <Stat label="Topics" value={stats.data.topics} tone="muted" hint="source topics seen" />
        </div>
      )}

      {lens === "topics" ? (
        <Panel
          title="Source topics"
          meta={topics.data ? `${topics.data.length} topics` : undefined}
          bodyClassName="p-0"
        >
          {topics.isPending && <Spinner />}
          {topics.error && <ErrorState error={topics.error} />}
          {topics.data?.length === 0 && (
            <EmptyState title="Nothing dead-lettered" hint="Every consumer is keeping up." />
          )}
          {Boolean(topics.data?.length) && <ColumnHeader lens="topics" />}
          <ul className="divide-y divide-border/60">
            {topics.data?.map((topic) => (
              <li key={topic.sourceTopic}>
                <Link
                  href={`/topics/${encodeURIComponent(topic.sourceTopic)}`}
                  className="flex items-center gap-5 px-5 py-4 transition hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-base font-medium leading-6">
                      {topic.sourceTopic}
                    </p>
                    <p className="truncate text-sm leading-6 text-muted-foreground">
                      {serviceOf(topic.sourceTopic)} · {topic.count} failure
                      {topic.count === 1 ? "" : "s"} · last {relAge(topic.lastSeenAt)} ago
                    </p>
                  </div>
                  <Chip icon={Layers} title="distinct error groups" className="w-14 justify-center">
                    {topic.groups}
                  </Chip>
                  {/* Lag is the consuming service's own group, and it is
                      best-effort: a dash means Kafka could not answer, not zero. */}
                  <Chip
                    icon={Radio}
                    tone={topic.lag && topic.lag > 0 ? "warning" : "neutral"}
                    title="consumer lag on this topic"
                    className="w-14 justify-center"
                  >
                    {topic.lag ?? "—"}
                  </Chip>
                  <CountsBar counts={topic.counts} />
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      ) : (
        <Panel
          title="Error groups — across every topic"
          meta={groups.data ? `${groups.data.length} groups` : undefined}
          bodyClassName="p-0"
        >
          {groups.isPending && <Spinner />}
          {groups.error && <ErrorState error={groups.error} />}
          {groups.data?.length === 0 && <EmptyState title="No errors recorded" />}
          {Boolean(groups.data?.length) && <ColumnHeader lens="errors" />}
          <ul className="divide-y divide-border/60">
            {groups.data?.map((group) => (
              <GroupRow key={group.fingerprint} group={group} href={`/groups/${group.fingerprint}`} />
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

/**
 * Short forms for the status columns.
 *
 * "Replayed" and "Discarded" are wider than the count they label — spelled out
 * they run into each other and into "Last". The full word is one hover away on
 * the `title`, and the dot beneath each is already the primary signal.
 */
const STATUS_ABBR: Record<Status, string> = {
  NEW: "New",
  REPLAYED: "Rpl",
  DISCARDED: "Dsc",
};

/**
 * The list's column legend.
 *
 * The right-hand columns are icons and coloured dots, which is fast to scan
 * once you know them and opaque until you do — the header is what makes the
 * first read possible without hovering every chip for its tooltip. Hidden below
 * `sm`, where the columns wrap anyway.
 *
 * Every width here is paired with one in the row beneath it (`w-14` chips,
 * `w-10` counts, `w-14` age, `w-4` chevron): the header is only honest as long
 * as the two agree, so change them together.
 */
function ColumnHeader({ lens }: { lens: "topics" | "errors" }) {
  return (
    <div className="hidden items-center gap-5 border-b border-border/60 bg-muted/40 px-5 py-2 sm:flex">
      <span className="min-w-0 flex-1">
        <Eyebrow>{lens === "topics" ? "Topic" : "Error"}</Eyebrow>
      </span>
      <Eyebrow className="block w-14 text-center">
        {lens === "topics" ? "Groups" : "Seen"}
      </Eyebrow>
      <Eyebrow className="block w-14 text-center">{lens === "topics" ? "Lag" : "Topics"}</Eyebrow>
      <span className="flex items-center gap-3">
        {(Object.keys(STATUS_META) as Status[]).map((status) => (
          <span key={status} title={STATUS_META[status].label} className="label-caps block w-10">
            {STATUS_ABBR[status]}
          </span>
        ))}
      </span>
      {/* Topic rows carry their age in the sub-line, so only the error list has
          a column here. */}
      {lens === "errors" && <Eyebrow className="block w-14 text-right">Last</Eyebrow>}
      <span className="w-4 shrink-0" aria-hidden />
    </div>
  );
}

/**
 * One headline count.
 *
 * Big enough to read from a standing desk — this strip is the reason the page
 * gets opened at all. The tone-hued rule down the left carries the status
 * colour, and NEW pairs it with a glyph so the one urgent card is never colour
 * alone.
 */
function Stat({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number;
  tone: "warning" | "success" | "muted";
  hint: string;
}) {
  const color =
    tone === "warning" ? "text-warning" : tone === "success" ? "text-success" : "text-foreground";
  const edge =
    tone === "warning" ? "bg-warning" : tone === "success" ? "bg-success" : "bg-muted-foreground/40";
  return (
    <Card className="flex items-stretch gap-4 p-5">
      <span aria-hidden className={cx("w-1 shrink-0 rounded-full", edge)} />
      <div className="min-w-0">
        <Eyebrow>{label}</Eyebrow>
        <p className={cx("mt-1.5 font-display text-5xl font-semibold tabular-nums leading-none", color)}>
          {value}
          {tone === "warning" && value > 0 && (
            <AlertTriangle className="ml-2.5 inline h-6 w-6 align-baseline" />
          )}
        </p>
        <p className="mt-2 truncate text-sm text-muted-foreground">{hint}</p>
      </div>
    </Card>
  );
}
