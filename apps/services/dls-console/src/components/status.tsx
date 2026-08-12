// Single source of truth for how a message Status looks — icon + tone — so the
// badge, count chips and stat strip stay consistent. Color is never the only
// signal: every status pairs a lucide glyph with its hue.
//
// "Dispatch" rule: green is the single "cleared" note, so REPLAYED (a completed
// forward action) is the only green; NEW draws attention in amber; DISCARDED
// recedes to graphite. Destructive red stays reserved for failures.
import { Archive, CheckCircle2, CircleDot, type LucideIcon } from "lucide-react";

import type { Status } from "@/lib/types";

export type StatusMeta = {
  label: string;
  Icon: LucideIcon;
  /** badge (soft fill + ring) */
  badge: string;
  /** solid dot for count chips */
  dot: string;
  /** bare text hue */
  text: string;
  /** ticket-stub edge — the status-hued left bar carried across every row/card */
  edge: string;
};

export const STATUS_META: Record<Status, StatusMeta> = {
  NEW: {
    label: "New",
    Icon: CircleDot,
    badge: "bg-warning/10 text-warning ring-warning/25",
    dot: "bg-warning",
    text: "text-warning",
    edge: "bg-warning",
  },
  REPLAYED: {
    label: "Replayed",
    Icon: CheckCircle2,
    badge: "bg-success/10 text-success ring-success/25",
    dot: "bg-success",
    text: "text-success",
    edge: "bg-success",
  },
  DISCARDED: {
    label: "Discarded",
    Icon: Archive,
    badge: "bg-muted text-muted-foreground ring-border",
    dot: "bg-muted-foreground/60",
    text: "text-muted-foreground",
    edge: "bg-muted-foreground/40",
  },
};
