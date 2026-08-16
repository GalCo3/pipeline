"use client";

import { Braces, Plus, Type, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Button, Input } from "@/components/ui";

/**
 * A record edited as a list of fields rather than as a blob of JSON.
 *
 * Replay forms are filled in by an operator reading a message, not by someone
 * authoring a document: the question is always "what is this key, and what
 * should it say instead", which a name/value row answers directly and a JSON
 * textarea answers only after the reader has counted braces. Editing a payload
 * as text also fails the whole form on a stray comma somewhere unrelated to the
 * change; a row can only be wrong about itself.
 *
 * Each row carries its own kind so a value's *type* survives an edit:
 *
 * - `text` — the value is a string, and whatever is typed stays a string.
 *   `PENDING`, `4`, `true` and `{"a": 1}` all come back out as strings.
 * - `json` — the value is anything else (number, boolean, null, array, object)
 *   and the cell is parsed as JSON, so it can only be committed while it parses.
 *
 * The kind is derived from the value the record arrived with, which is what
 * keeps a round-trip lossless: a string field cannot silently become a number
 * because the operator happened to type digits into it. New rows start as text
 * and can be switched with the per-row toggle.
 */

export type FieldsValue = Record<string, unknown>;

type Row = {
  /** stable across renders — the array index would reorder inputs on delete */
  id: number;
  name: string;
  kind: "text" | "json";
  text: string;
};

function rowsOf(record: FieldsValue, nextId: () => number): Row[] {
  return Object.entries(record).map(([name, value]) =>
    typeof value === "string"
      ? { id: nextId(), name, kind: "text" as const, text: value }
      : { id: nextId(), name, kind: "json" as const, text: JSON.stringify(value) ?? "null" },
  );
}

/** The record the rows describe, or the first reason they don't describe one. */
function recordOf(rows: Row[]): { value: FieldsValue | undefined; error: string | null } {
  const out: FieldsValue = {};
  for (const row of rows) {
    const name = row.name.trim();
    // A nameless row is a row mid-typing, not an error to shout about — it is
    // simply not part of the record yet.
    if (!name) continue;
    if (name in out) return { value: undefined, error: `duplicate field "${name}"` };
    if (row.kind === "text") {
      out[name] = row.text;
      continue;
    }
    try {
      out[name] = JSON.parse(row.text);
    } catch {
      return { value: undefined, error: `"${name}" is not valid JSON` };
    }
  }
  return { value: out, error: null };
}

export function FieldsEditor({
  initial,
  onChange,
  /** headers are a flat string map on the wire — no kind toggle, no JSON rows */
  stringsOnly = false,
  addLabel = "Add field",
  emptyHint,
}: {
  initial: FieldsValue;
  onChange: (value: FieldsValue | undefined, error: string | null) => void;
  stringsOnly?: boolean;
  addLabel?: string;
  emptyHint?: string;
}) {
  const counter = useRef(0);
  const nextId = () => ++counter.current;
  const [rows, setRows] = useState<Row[]>(() => rowsOf(initial, nextId));
  const [error, setError] = useState<string | null>(null);

  function apply(next: Row[]) {
    setRows(next);
    const { value, error: nextError } = recordOf(next);
    setError(nextError);
    onChange(value, nextError);
  }

  const update = (id: number, patch: Partial<Row>) =>
    apply(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));

  // Nesting is real in these payloads, and a `json` row's value can be several
  // lines of it — a textarea that grows with its content beats a single-line
  // input that hides the tail behind a scroll position.
  const rowsWithSpan = useMemo(
    () => rows.map((row) => ({ row, tall: row.kind === "json" && row.text.length > 60 })),
    [rows],
  );

  return (
    <div className="space-y-2">
      {rows.length === 0 && emptyHint && (
        <p className="text-xs text-muted-foreground">{emptyHint}</p>
      )}

      {rowsWithSpan.map(({ row, tall }) => (
        <div key={row.id} className="flex items-start gap-2">
          <Input
            className="w-1/3 shrink-0 font-mono text-xs"
            placeholder="name"
            value={row.name}
            spellCheck={false}
            aria-label="Field name"
            onChange={(e) => update(row.id, { name: e.target.value })}
          />

          {tall ? (
            <textarea
              rows={3}
              spellCheck={false}
              value={row.text}
              aria-label={`Value of ${row.name || "field"}`}
              onChange={(e) => update(row.id, { text: e.target.value })}
              className="code-pane scrollbar-thin min-w-0 flex-1 rounded-md p-2 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          ) : (
            <Input
              className="min-w-0 flex-1 font-mono text-xs"
              placeholder={row.kind === "json" ? "JSON value" : "value"}
              value={row.text}
              spellCheck={false}
              aria-label={`Value of ${row.name || "field"}`}
              onChange={(e) => update(row.id, { text: e.target.value })}
            />
          )}

          {!stringsOnly && (
            <Button
              size="sm"
              icon={row.kind === "json" ? Braces : Type}
              title={
                row.kind === "json"
                  ? "JSON value — parsed as typed"
                  : "Text value — sent as a string"
              }
              aria-label="Toggle value kind"
              onClick={() => update(row.id, { kind: row.kind === "json" ? "text" : "json" })}
            />
          )}

          <Button
            size="sm"
            icon={X}
            aria-label={`Remove ${row.name || "field"}`}
            onClick={() => apply(rows.filter((other) => other.id !== row.id))}
          />
        </div>
      ))}

      <div className="flex items-center gap-3">
        <Button
          size="sm"
          icon={Plus}
          onClick={() => apply([...rows, { id: nextId(), name: "", kind: "text", text: "" }])}
        >
          {addLabel}
        </Button>
        {error && <span className="text-xs text-destructive">{error}</span>}
      </div>
    </div>
  );
}
