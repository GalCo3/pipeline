"use client";

import { useMemo, useState } from "react";

import type { RecordOverrides } from "@/lib/types";
import { Eyebrow, Input } from "@/components/ui";

/**
 * The three record-level fields every replay form offers: where it goes, what
 * key it carries, what headers ride with it.
 *
 * Shared by the single-message edit modal and the bulk one so a replay is
 * described the same way whether it is aimed at one document or a thousand —
 * the single screen used to grow a stray target-topic box beside its buttons,
 * which meant the same decision lived in two places with two different shapes.
 *
 * None of these three is *restored*: a DLS document keeps the decoded value and
 * nothing else, so an empty key field means "produce keyless" (which is how the
 * pipeline itself produces) rather than "reuse the original".
 */

export type OverridesState = {
  key: string;
  setKey: (value: string) => void;
  headersText: string;
  setHeadersText: (value: string) => void;
  targetTopic: string;
  setTargetTopic: (value: string) => void;
  /** parsed headers, or `undefined` while the JSON is unparseable */
  headers: Record<string, string> | undefined;
  headersError: string | null;
  /** false while a field is mid-edit and invalid — the caller disables commit */
  valid: boolean;
  /** only the fields the operator actually filled in */
  overrides: RecordOverrides;
};

/** Live-validated state for the three fields. */
export function useRecordOverrides(): OverridesState {
  const [key, setKey] = useState("");
  const [headersText, setHeadersText] = useState("");
  const [targetTopic, setTargetTopic] = useState("");

  const { headers, headersError } = useMemo(() => parseHeaders(headersText), [headersText]);

  return {
    key,
    setKey,
    headersText,
    setHeadersText,
    targetTopic,
    setTargetTopic,
    headers,
    headersError,
    valid: headersError === null,
    overrides: {
      key: key || null,
      headers: headers && Object.keys(headers).length ? headers : null,
      targetTopic: targetTopic || null,
    },
  };
}

/**
 * Headers are a flat string map because that is what a Kafka header is on the
 * wire; a nested value would have to be stringified on the way out anyway, and
 * silently doing that would hide it from the operator who typed it.
 */
function parseHeaders(text: string): {
  headers: Record<string, string> | undefined;
  headersError: string | null;
} {
  if (!text.trim()) return { headers: {}, headersError: null };
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    return {
      headers: undefined,
      headersError: error instanceof Error ? error.message : "invalid JSON",
    };
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { headers: undefined, headersError: "headers must be a JSON object" };
  }
  const out: Record<string, string> = {};
  for (const [name, value] of Object.entries(parsed)) {
    if (typeof value !== "string") {
      return { headers: undefined, headersError: `header "${name}" must be a string` };
    }
    out[name] = value;
  }
  return { headers: out, headersError: null };
}

export function RecordOverridesFields({
  state,
  topicPlaceholder,
  topicHint,
}: {
  state: OverridesState;
  topicPlaceholder: string;
  topicHint: string;
}) {
  return (
    <div className="space-y-4">
      <div>
        <Eyebrow>Produced to</Eyebrow>
        <Input
          className="mt-1 w-full font-mono"
          placeholder={topicPlaceholder}
          value={state.targetTopic}
          onChange={(e) => state.setTargetTopic(e.target.value)}
          aria-label="Target topic"
        />
        <p className="mt-1 text-xs text-muted-foreground">{topicHint}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Eyebrow>Record key (id)</Eyebrow>
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

        <div>
          <Eyebrow>Headers</Eyebrow>
          <textarea
            rows={3}
            spellCheck={false}
            value={state.headersText}
            onChange={(e) => state.setHeadersText(e.target.value)}
            placeholder={'{"x-source": "console"}'}
            aria-label="Headers"
            className="code-pane scrollbar-thin mt-1 w-full rounded-md p-3 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {state.headersError ? (
            <p className="mt-1 text-xs text-destructive">{state.headersError}</p>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">
              JSON object of strings. <span className="font-mono">x-dls-replay-of</span> is added
              automatically.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
