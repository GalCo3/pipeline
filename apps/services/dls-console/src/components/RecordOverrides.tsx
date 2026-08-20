"use client";

import { useState } from "react";

import type { RecordOverrides } from "@/lib/types";
import { PayloadEditor } from "@/components/Json";
import { Eyebrow, Input } from "@/components/ui";

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/**
 * Headers go out as a flat string map — a value that parsed as something else
 * (a number, an object, ...) is stringified on the way out, same as it would
 * be if typed as a string literally.
 */
function stringifyValues(value: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(value).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)]),
  );
}

/**
 * The record-level fields a replay form offers: where it goes, what key it
 * carries, what headers ride with it.
 *
 * Shared by the single-message edit modal and the bulk one so a replay is
 * described the same way whether it is aimed at one document or a thousand —
 * the single screen used to grow a stray target-topic box beside its buttons,
 * which meant the same decision lived in two places with two different shapes.
 *
 * The key is single-message only (`showKey`). It chooses the partition, so one
 * key applied across a bulk replay would funnel every message in the batch onto
 * one partition — a batch-wide key is a footgun with no use case behind it.
 *
 * None of these is *restored*: a DLS document keeps the decoded value and
 * nothing else, so an empty key field means "produce keyless" (which is how the
 * pipeline itself produces) rather than "reuse the original".
 */

export type OverridesState = {
  key: string;
  setKey: (value: string) => void;
  headersText: string;
  setHeadersText: (value: string) => void;
  /** parsed + stringified headers, or `undefined` while the JSON is invalid/not an object */
  headers: Record<string, string> | undefined;
  /** only for shapes `PayloadEditor`'s own syntax check can't catch — valid JSON that isn't an object */
  headersShapeError: string | null;
  targetTopic: string;
  setTargetTopic: (value: string) => void;
  /** false while the headers JSON is mid-edit and invalid — the caller disables commit */
  valid: boolean;
  /** only the fields the operator actually filled in */
  overrides: RecordOverrides;
};

/** Live-validated state for the record-level fields. */
export function useRecordOverrides(): OverridesState {
  const [key, setKey] = useState("");
  const [targetTopic, setTargetTopic] = useState("");
  const [headersText, setHeadersTextState] = useState("");
  const [headers, setHeaders] = useState<Record<string, string> | undefined>({});
  const [headersShapeError, setHeadersShapeError] = useState<string | null>(null);

  function setHeadersText(text: string) {
    setHeadersTextState(text);
    if (!text.trim()) {
      // Untouched (or cleared back to empty) means "no extra headers", not
      // "invalid JSON" — the placeholder shows `{}` but nothing is sent.
      setHeaders({});
      setHeadersShapeError(null);
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      // Syntax errors are shown by `PayloadEditor` itself, right under the
      // textarea — nothing more to say here.
      setHeaders(undefined);
      setHeadersShapeError(null);
      return;
    }
    if (!isPlainObject(parsed)) {
      setHeaders(undefined);
      setHeadersShapeError("Headers must be a JSON object.");
      return;
    }
    setHeaders(stringifyValues(parsed));
    setHeadersShapeError(null);
  }

  return {
    key,
    setKey,
    headersText,
    setHeadersText,
    headers,
    headersShapeError,
    targetTopic,
    setTargetTopic,
    valid: headers !== undefined,
    overrides: {
      key: key || null,
      headers: headers && Object.keys(headers).length ? headers : null,
      targetTopic: targetTopic || null,
    },
  };
}

/**
 * Three independent sections — topic, key, headers — kept separate (rather
 * than one fixed-order block) so a caller can interleave them with its own
 * payload field: the single-message panel wants topic, key, value, headers;
 * bulk has no key at all.
 */

export function TargetTopicField({
  state,
  placeholder,
  hint,
}: {
  state: OverridesState;
  placeholder: string;
  hint: string;
}) {
  return (
    <div>
      <Eyebrow>Topic</Eyebrow>
      <Input
        className="mt-1 w-full font-mono"
        placeholder={placeholder}
        value={state.targetTopic}
        onChange={(e) => state.setTargetTopic(e.target.value)}
        aria-label="Target topic"
      />
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

export function RecordKeyField({ state }: { state: OverridesState }) {
  return (
    <div>
      <Eyebrow>Key</Eyebrow>
      <Input
        className="mt-1 w-full font-mono"
        placeholder="none — produced keyless"
        value={state.key}
        onChange={(e) => state.setKey(e.target.value)}
        aria-label="Record key"
      />
      <p className="mt-1 text-xs text-muted-foreground">
        Chooses the partition. The original key was never stored, so empty means keyless.
      </p>
    </div>
  );
}

export function HeadersField({ state }: { state: OverridesState }) {
  return (
    <div>
      <Eyebrow>Headers</Eyebrow>
      <div className="mt-1">
        <PayloadEditor
          value={state.headersText}
          rows={4}
          placeholder="{}"
          onChange={(text) => state.setHeadersText(text)}
        />
      </div>
      {state.headersShapeError && (
        <p className="mt-1 text-xs text-destructive">{state.headersShapeError}</p>
      )}
      <p className="mt-1 text-xs text-muted-foreground">
        A flat JSON object of strings. <span className="font-mono">x-dls-replay-of</span> is added
        automatically.
      </p>
    </div>
  );
}
