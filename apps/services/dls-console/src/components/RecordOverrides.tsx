"use client";

import { useState } from "react";

import type { RecordOverrides } from "@/lib/types";
import { FieldsEditor } from "@/components/Fields";
import { Eyebrow, Input } from "@/components/ui";

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
  /** parsed headers, or `undefined` while a row is invalid */
  headers: Record<string, string> | undefined;
  setHeaders: (value: Record<string, string> | undefined) => void;
  headersError: string | null;
  setHeadersError: (value: string | null) => void;
  targetTopic: string;
  setTargetTopic: (value: string) => void;
  /** false while a field is mid-edit and invalid — the caller disables commit */
  valid: boolean;
  /** only the fields the operator actually filled in */
  overrides: RecordOverrides;
};

/** Live-validated state for the record-level fields. */
export function useRecordOverrides(): OverridesState {
  const [key, setKey] = useState("");
  const [targetTopic, setTargetTopic] = useState("");
  const [headers, setHeaders] = useState<Record<string, string> | undefined>({});
  const [headersError, setHeadersError] = useState<string | null>(null);

  return {
    key,
    setKey,
    headers,
    headersError,
    setHeaders,
    setHeadersError,
    targetTopic,
    setTargetTopic,
    valid: headersError === null,
    overrides: {
      key: key || null,
      headers: headers && Object.keys(headers).length ? headers : null,
      targetTopic: targetTopic || null,
    },
  };
}

export function RecordOverridesFields({
  state,
  topicPlaceholder,
  topicHint,
  showKey = true,
}: {
  state: OverridesState;
  topicPlaceholder: string;
  topicHint: string;
  showKey?: boolean;
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

      {showKey && (
        <div>
          <Eyebrow>Record key</Eyebrow>
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
      )}

      <div>
        <Eyebrow>Headers</Eyebrow>
        <div className="mt-1">
          {/* Kafka headers are a flat string map on the wire, so every value is
              a string — a nested one would have to be stringified on the way
              out anyway, and doing that silently would hide it from whoever
              typed it. */}
          <FieldsEditor
            stringsOnly
            initial={{}}
            addLabel="Add header"
            emptyHint="No extra headers."
            onChange={(value, error) => {
              state.setHeaders(value as Record<string, string> | undefined);
              state.setHeadersError(error);
            }}
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          <span className="font-mono">x-dls-replay-of</span> is added automatically.
        </p>
      </div>
    </div>
  );
}
