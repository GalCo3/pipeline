"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { prettyJson } from "@/lib/format";

/** Read-only JSON pane. Dark in both themes — a payload reads as terminal output. */
export function JsonView({ value, className }: { value: unknown; className?: string }) {
  const text = prettyJson(value);
  return (
    <div className={`relative ${className ?? ""}`}>
      <CopyButton text={text} />
      <pre className="code-pane scrollbar-thin max-h-96 overflow-auto rounded-md p-3 text-xs leading-relaxed">
        {text}
      </pre>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      aria-label="Copy"
      className="absolute right-2 top-2 rounded border border-white/10 bg-white/5 p-1 text-code-foreground/70 transition hover:text-code-foreground"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

/**
 * Editable JSON with live validation.
 *
 * The parse result is reported upward on every keystroke so the caller can
 * disable its commit button: producing invalid JSON to a topic the services
 * consume as JSON would just dead-letter it again on arrival.
 */
export function PayloadEditor({
  value,
  onChange,
  rows = 16,
  placeholder,
}: {
  value: string;
  onChange: (text: string, parsed: unknown | undefined) => void;
  rows?: number;
  placeholder?: string;
}) {
  const [error, setError] = useState<string | null>(null);

  return (
    <div>
      <textarea
        rows={rows}
        value={value}
        placeholder={placeholder}
        spellCheck={false}
        onChange={(e) => {
          const text = e.target.value;
          try {
            const parsed = JSON.parse(text);
            setError(null);
            onChange(text, parsed);
          } catch (err) {
            setError(err instanceof Error ? err.message : "invalid JSON");
            onChange(text, undefined);
          }
        }}
        className="code-pane scrollbar-thin w-full rounded-md p-3 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  );
}
