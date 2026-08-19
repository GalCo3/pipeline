"use client";

import { Heart, Skull } from "lucide-react";
import { useEffect, useState } from "react";

import { cx } from "@/lib/format";

/**
 * Page footer — the console's signature line, plus a couple of things to find.
 *
 * The eggs are deliberately inert: they change a line of text and nothing else.
 * Nothing here touches the store, the session or any request, so the worst an
 * operator can do by poking at the footer during an incident is read a joke.
 *
 * Three of them:
 *  - click the skull  → cycles the dead-letter epitaphs
 *  - the konami code  → a second-chance line, the one nod to what replay does
 *  - the console      → a greeting on first mount, for whoever opens devtools
 */

const EPITAPHS = [
  "Here lie the messages that could not be delivered.",
  "Every one of these was somebody's happy path.",
  "A dead letter is only dead until someone reads it.",
  "No message left behind — some just take a second attempt.",
  "The queue forgives. The consumer does not.",
  "Offsets committed, hopes deferred.",
];

const KONAMI = [
  "ArrowUp",
  "ArrowUp",
  "ArrowDown",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "ArrowLeft",
  "ArrowRight",
  "b",
  "a",
];

export function Footer({ store }: { store: string }) {
  const [epitaph, setEpitaph] = useState<number | null>(null);
  const [secondChance, setSecondChance] = useState(false);

  // One greeting per mount, for whoever has devtools open anyway.
  useEffect(() => {
    console.log(
      "%cDLS Console%c — dead letter triage for the hermes pipeline\nBuilt by Gal Cohen. Try the skull. Then try the konami code.",
      "font-weight:bold;font-size:13px",
      "font-weight:normal",
    );
  }, []);

  useEffect(() => {
    let at = 0;
    function onKey(event: KeyboardEvent) {
      // Ignore anything typed into a field — an operator editing a payload must
      // never trip this.
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA)$/.test(target.tagName)) return;
      const want = KONAMI[at];
      at = event.key.toLowerCase() === want.toLowerCase() ? at + 1 : 0;
      if (at === KONAMI.length) {
        at = 0;
        setSecondChance(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const line = secondChance
    ? "↑ ↑ ↓ ↓ ← → ← → B A — everything in here gets a second chance."
    : epitaph === null
      ? `${store} · one document per failure, nothing merged, nothing lost.`
      : EPITAPHS[epitaph];

  return (
    <footer className="mt-12 border-t border-border/70 bg-card/40">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-5">
        <p className="flex items-center gap-2.5 text-sm text-muted-foreground">
          <button
            type="button"
            onClick={() => setEpitaph((n) => (n === null ? 0 : (n + 1) % EPITAPHS.length))}
            aria-label="Read an epitaph"
            className={cx(
              "-m-2 rounded-md p-2 text-muted-foreground transition hover:text-brand",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              secondChance && "text-brand",
            )}
          >
            <Skull className="h-4 w-4" />
          </button>
          {/* aria-live, not a silent swap: the line is the whole point of the
              control that changes it. */}
          <span aria-live="polite">{line}</span>
        </p>

        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          Developed with
          <Heart className="h-4 w-4 text-destructive" aria-label="love" />
          by
          <span className="font-medium text-foreground">Gal Cohen</span>
        </p>
      </div>
    </footer>
  );
}
