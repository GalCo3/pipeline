"use client";

// Token-driven UI primitives for the "Dispatch" console. Everything keys off the
// semantic Tailwind colors (brand / primary / muted / destructive), so light,
// dark and future rethemes stay free. Reach for these instead of hand-rolling
// button/card/badge classes per screen.
import { Check, ChevronDown, Loader2, type LucideIcon } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from "react";

import { compactNum, cx, fullNum } from "@/lib/format";
import type { Status, StatusCounts } from "@/lib/types";
import { STATUS_META } from "@/components/status";

// ---- Button --------------------------------------------------------------
// brand = forward action (replay / dispatch onward). primary = ink default.
// secondary = neutral fill. ghost = bordered/quiet. danger/destructive = discard.
type Variant = "brand" | "primary" | "secondary" | "ghost" | "danger" | "destructive";
type Size = "sm" | "md";

const VARIANT: Record<Variant, string> = {
  brand:
    "bg-brand text-brand-foreground shadow-sm hover:shadow-brand hover:brightness-105 active:scale-[0.98]",
  primary: "bg-primary text-primary-foreground hover:brightness-110 active:scale-[0.98]",
  secondary: "bg-secondary text-secondary-foreground hover:bg-accent active:scale-[0.98]",
  ghost: "border border-border bg-card text-foreground hover:bg-accent active:scale-[0.98]",
  // Quiet: bordered red text, fills on hover — for inline list actions.
  danger:
    "border border-destructive/30 bg-card text-destructive hover:bg-destructive hover:text-destructive-foreground active:scale-[0.98]",
  // Loud: solid red — for confirm-dialog commit buttons.
  destructive: "bg-destructive text-destructive-foreground hover:brightness-110 active:scale-[0.98]",
};

const SIZE: Record<Size, string> = {
  sm: "h-8 px-2.5 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "ghost", size = "md", icon: Icon, loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        "disabled:pointer-events-none disabled:opacity-40",
        SIZE[size],
        VARIANT[variant],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className={size === "sm" ? "h-3.5 w-3.5 animate-spin" : "h-4 w-4 animate-spin"} />
      ) : (
        Icon && <Icon className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} />
      )}
      {children}
    </button>
  );
});

// ---- Card / Panel --------------------------------------------------------
export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-lg border border-border/70 bg-card text-card-foreground shadow-sm",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

/**
 * A titled card section with a mono console-label header and an accent tick.
 *
 * `meta` is the quiet right-hand fact about the panel's own contents — a row
 * count, a scope — kept apart from `action` so a caption never has to be
 * dressed as a control just to sit in the header. A panel whose body is a
 * table-like list gets its column labels from a header row inside the body
 * (see `ColumnHeader` on the overview page) rather than from this bar, so
 * that row can match the data rows' flex structure exactly — mixing column
 * labels into this title bar's own layout would throw that match off.
 */
export function Panel({
  title,
  leftMeta,
  meta,
  action,
  children,
  bodyClassName,
}: {
  title: string;
  /** quiet fact appended right after the title, e.g. a row count — left side, unlike `meta` */
  leftMeta?: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  bodyClassName?: string;
}) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3">
        <span className="flex items-center gap-2.5">
          <span className="h-4 w-1 rounded-full bg-brand/80" />
          <Eyebrow>{title}</Eyebrow>
          {leftMeta && <span className="text-sm tabular-nums text-muted-foreground">{leftMeta}</span>}
        </span>
        <span className="flex items-center gap-3">
          {meta && <span className="text-sm tabular-nums text-muted-foreground">{meta}</span>}
          {action}
        </span>
      </div>
      <div className={cx("p-5", bodyClassName)}>{children}</div>
    </Card>
  );
}

/** Mono uppercase wide-tracked console label. Structural, quiet. */
export function Eyebrow({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cx("label-caps", className)}>{children}</span>;
}

// ---- Status ---------------------------------------------------------------
export function StatusBadge({ status, size = "md" }: { status: Status; size?: Size }) {
  const meta = STATUS_META[status];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full font-medium ring-1 ring-inset",
        size === "sm" ? "px-1.5 py-0.5 text-[0.65rem]" : "px-2 py-0.5 text-xs",
        meta.badge,
      )}
    >
      <meta.Icon className="h-3 w-3" />
      {meta.label}
    </span>
  );
}

/**
 * The signature: a status-hued ticket stub down the left of every row and card,
 * so status reads before any text does.
 */
export function StatusEdge({ status, className }: { status: Status; className?: string }) {
  return (
    <span
      aria-hidden
      className={cx("block w-1 shrink-0 self-stretch rounded-full", STATUS_META[status].edge, className)}
    />
  );
}

/**
 * Compact NEW/REPLAYED/DISCARDED tally, zero-counts dimmed rather than hidden.
 *
 * Each count leads with that status's own glyph (`STATUS_META[status].Icon`)
 * rather than a bare color dot — the same New/Replayed/Discarded icons the
 * badge and the edge stripe use elsewhere, so a count reads as "3 replayed"
 * without needing the color alone to carry which status it is.
 */
export function CountsBar({ counts }: { counts: StatusCounts }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-3 tabular-nums">
      {(Object.keys(STATUS_META) as Status[]).map((status) => {
        const count = counts[status] ?? 0;
        const meta = STATUS_META[status];
        return (
          <span
            key={status}
            title={`${meta.label} · ${fullNum(count)}`}
            // Fixed width, tabular figures: three of these sit in a column down
            // a list, and one row's count must not shove the next one sideways.
            // The count is shortened rather than allowed to outgrow the box —
            // millions of dead letters is an ordinary reading here.
            className={cx(
              "inline-flex w-20 shrink-0 items-center gap-1.5 whitespace-nowrap text-sm font-medium",
              count ? "text-foreground" : "text-muted-foreground/40",
            )}
          >
            <meta.Icon className={cx("h-3.5 w-3.5 shrink-0", count ? meta.text : "text-muted-foreground/40")} />
            {compactNum(count)}
          </span>
        );
      })}
    </span>
  );
}

// ---- Small parts ----------------------------------------------------------
type ChipTone = "neutral" | "warning" | "brand" | "info";
const CHIP_TONE: Record<ChipTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  warning: "bg-warning/10 text-warning",
  brand: "bg-brand/10 text-brand",
  info: "bg-info/10 text-info",
};

export function Chip({
  tone = "neutral",
  icon: Icon,
  mono = false,
  title,
  className,
  children,
}: {
  tone?: ChipTone;
  icon?: LucideIcon;
  mono?: boolean;
  title?: string;
  /** for column alignment — a list gives every chip in a column one width */
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-sm px-2 py-1 text-sm font-medium tabular-nums",
        mono && "font-mono",
        CHIP_TONE[tone],
        className,
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}
      {children}
    </span>
  );
}

/** The console's view/lens toggle — shared so every switch reads identically. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<[T, string]>;
}) {
  return (
    <div className="inline-flex rounded-md border border-border bg-card p-1 text-[0.9375rem]">
      {options.map(([v, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          aria-pressed={value === v}
          // h-9: this is the screen's primary control, so it clears the 36px
          // pointer target rather than sitting at label height.
          className={cx(
            "inline-flex h-9 items-center rounded-[0.3rem] px-4 font-medium transition",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            value === v
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cx(
        "h-9 rounded-md border border-input bg-card px-3 text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        props.className,
      )}
    />
  );
}

/**
 * A "toggle menu": a button that opens a checklist popover, for filters where
 * more than one value can be picked at once. Every filter in the overview
 * header (topic, error, status) uses this same control so they read as one
 * family rather than three different widgets.
 */
export function MultiSelect({
  label,
  placeholder,
  options,
  selected,
  onChange,
  className,
}: {
  label: string;
  /** shown on the trigger when nothing is selected */
  placeholder: string;
  options: Array<{ value: string; label: string; icon?: LucideIcon }>;
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle(value: string) {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(next);
  }

  // Every box checked reads as "don't narrow" — the plain placeholder — but
  // every box unchecked is a real, distinct choice ("show nothing") and has
  // to read differently, or a deliberate empty selection looks identical to
  // the unfiltered default.
  const allChecked = options.length > 0 && selected.size === options.length;
  const noneChecked = options.length > 0 && selected.size === 0;
  // Only a single checked box has one specific option to show an icon for —
  // "3 selected" or the placeholder text has no one option to represent.
  const soleSelected =
    !allChecked && !noneChecked && selected.size === 1
      ? options.find((o) => o.value === [...selected][0])
      : undefined;
  const SoleIcon = soleSelected?.icon;
  const summary = allChecked
    ? placeholder
    : noneChecked
      ? "None"
      : selected.size === 0
        ? placeholder
        : (soleSelected?.label ?? `${selected.size} selected`);

  return (
    <div ref={rootRef} className={cx("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        className={cx(
          "flex h-9 w-full items-center gap-2 rounded-md border border-input bg-card px-2.5 text-sm",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          allChecked ? "text-muted-foreground" : "text-foreground",
        )}
      >
        {SoleIcon && <SoleIcon className="h-3.5 w-3.5 shrink-0" />}
        <span className="truncate">{summary}</span>
        <ChevronDown className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={label}
          aria-multiselectable="true"
          className="absolute left-0 top-full z-20 mt-1 max-h-72 w-max min-w-full overflow-auto rounded-md border border-border bg-card py-1 shadow-md"
        >
          {options.length === 0 && (
            <p className="px-3 py-1.5 text-sm text-muted-foreground">Nothing to pick</p>
          )}
          {options.length > 0 && (
            <button
              type="button"
              onClick={() => onChange(allChecked ? new Set() : new Set(options.map((o) => o.value)))}
              className="flex w-full items-center whitespace-nowrap border-b border-border/60 px-3 py-1.5 text-left text-sm font-medium text-brand hover:bg-accent/60"
            >
              {allChecked ? "Deselect all" : "Select all"}
            </button>
          )}
          {options.map((option) => {
            const checked = selected.has(option.value);
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={checked}
                onClick={() => toggle(option.value)}
                className="flex w-full items-center gap-2 whitespace-nowrap px-3 py-1.5 text-left text-sm hover:bg-accent/60"
              >
                <span
                  className={cx(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border",
                    checked ? "border-primary bg-primary text-primary-foreground" : "border-input",
                  )}
                >
                  {checked && <Check className="h-3 w-3" />}
                </span>
                {Icon && <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---- States ---------------------------------------------------------------
export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="py-16 text-center">
      <p className="font-display text-lg font-semibold text-foreground">{title}</p>
      {hint && <p className="mt-1.5 text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
      {message}
    </div>
  );
}

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  /** Omit to hide the page-size selector — callers that don't support it just skip the prop. */
  onPageSize?: (pageSize: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
      <span className="tabular-nums">
        {fullNum((page - 1) * pageSize + 1)}–{fullNum(Math.min(page * pageSize, total))} of{" "}
        {fullNum(total)}
      </span>
      <span className="flex items-center gap-3">
        {onPageSize && (
          <label className="flex items-center gap-1.5">
            Rows
            <select
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              className="h-7 rounded-md border border-input bg-card px-1.5 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="flex items-center gap-2">
          <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Prev
          </Button>
          <span className="tabular-nums">
            {page} / {pages}
          </span>
          <Button size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
            Next
          </Button>
        </span>
      </span>
    </div>
  );
}
