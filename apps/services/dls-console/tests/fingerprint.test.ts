import { describe, expect, it } from "vitest";

import { errorType, fingerprints, normalize } from "../src/lib/fingerprint";

describe("normalize", () => {
  it("masks the varying parts", () => {
    expect(normalize("doc 4a1f8e2c-1111-2222-3333-444455556666 missing")).toBe("doc <id> missing");
    expect(normalize("failed at 2026-08-11T09:15:00Z")).toBe("failed at <ts>");
    expect(normalize("offset 12345 of partition 3")).toBe("offset <n> of partition <n>");
    expect(normalize("digest a3f1c9d4e5b60718293a")).toBe("digest <hash>");
    expect(normalize("at 0x7fae12ab")).toBe("at <addr>");
  });

  it("collapses whitespace and tolerates null", () => {
    expect(normalize("  two   spaces\n")).toBe("two spaces");
    expect(normalize(null)).toBe("");
  });

  it("masks the writing service and its topic", () => {
    // Every service interpolates its own name into the message, so without this
    // the same bug in six services reads as six groups.
    expect(normalize("Failed to index cargo-lexical document 4", "cargo-lexical.files")).toBe(
      "Failed to index <svc> document <n>",
    );
    expect(normalize("no consumer on cargo-lexical.files", "cargo-lexical.files")).toBe(
      "no consumer on <topic>",
    );
    // Only the writer's own tokens are masked — a hyphenated word that merely
    // looks like a slug is left alone.
    expect(normalize("opened read-only", "cargo-lexical.files")).toBe("opened read-only");
  });

  it("collapses an echoed payload, keeping the description around it", () => {
    // A pydantic validation error prints the object it choked on, which is
    // different for every document and would make every group a group of one.
    const one =
      "1 validation error for ChatUserMessage _updatedAt Field required " +
      "[type=missing, input_value={'id': 7, 'name': 'bob'}, input_type=dict]";
    const two =
      "1 validation error for ChatUserMessage _updatedAt Field required " +
      "[type=missing, input_value={'id': 9, 'colour': 'green', 'roles': None}, input_type=dict]";
    expect(normalize(one)).toBe(normalize(two));
    expect(normalize(one)).toBe(
      "<n> validation error for ChatUserMessage _updatedAt Field required " +
        "[type=missing, input_value=<obj>, input_type=dict]",
    );
  });

  it("collapses a nested payload without eating the rest of the line", () => {
    expect(normalize("bad doc {'a': {'b': [1, 2]}} rejected")).toBe("bad doc <obj> rejected");
  });

  it("masks an opaque id that is neither a uuid, a digest nor a number", () => {
    // The pipeline's own ids look like this — letters and digits interleaved, so
    // the digest rule (all hex) and the number rule (word boundaries) both miss
    // them and every document hashes to its own group.
    expect(
      normalize("Failed to index chat-users-lexical document QMdvxJcvT4LzsCS9d", "chat-users-lexical.users"),
    ).toBe("Failed to index <svc> document <id>");
    expect(normalize("Failed to index chat-users-lexical document QMdvxJcvT4LzsCS9d", "chat-users-lexical.users")).toBe(
      normalize("Failed to index chat-users-lexical document 7fKp2aWqZzLm4Nb8x", "chat-users-lexical.users"),
    );
    // A plain word keeps its shape — the rule needs a digit AND a letter.
    expect(normalize("record not found")).toBe("record not found");
  });

  it("keeps a uuid whole through the number sweep", () => {
    // The general \d+ rule would otherwise shred a UUID into <n> fragments and
    // stop two occurrences of the same error from matching.
    expect(normalize("id 4a1f8e2c-1111-2222-3333-444455556666")).toBe("id <id>");
  });
});

describe("errorType", () => {
  it("reads the last traceback frame", () => {
    const stack = [
      "Traceback (most recent call last):",
      '  File "main.py", line 3, in <module>',
      "    raise ValueError('x')",
      "exceptions.CargoFileNotFoundError: file missing",
    ].join("\n");
    expect(errorType(stack, "file missing")).toBe("CargoFileNotFoundError");
  });

  it("falls back to a `Type: message` error string", () => {
    // `send_to_dls` records an empty stack when handed a plain string.
    expect(errorType("", "ValueError: boom")).toBe("ValueError");
    expect(errorType("", "no colon here")).toBeNull();
  });
});

describe("fingerprints", () => {
  it("collapses the same error with different ids", () => {
    const a = fingerprints({
      error: "Cargo file 4a1f8e2c-1111-2222-3333-444455556666 not found",
      errorStack: "CargoFileNotFoundError: missing",
      sourceTopic: "cargo-lexical.files",
    });
    const b = fingerprints({
      error: "Cargo file 9b2e7d3a-9999-8888-7777-666655554444 not found",
      errorStack: "CargoFileNotFoundError: missing",
      sourceTopic: "cargo-lexical.files",
    });
    expect(a).toEqual(b);
  });

  it("collapses one bug across services into one error group", () => {
    // The "by error" lens exists to answer *what is broken*; a message carrying
    // its own service name would keep six services in six rows forever.
    const cargo = fingerprints({
      error: "Failed to index cargo-lexical document 4",
      errorStack: "RuntimeError: index failed",
      sourceTopic: "cargo-lexical.files",
    });
    const chief = fingerprints({
      error: "Failed to index chief-lexical document 17",
      errorStack: "RuntimeError: index failed",
      sourceTopic: "chief-lexical.messages",
    });
    expect(cargo.errorFingerprint).toBe(chief.errorFingerprint);
    // Topic-scoped identity still separates them — the topic screen must not
    // start showing another service's failures.
    expect(cargo.fingerprint).not.toBe(chief.fingerprint);
  });

  it("scopes only the topic-scoped hash by topic", () => {
    const a = fingerprints({ error: "boom", errorStack: "ValueError: boom", sourceTopic: "t1" });
    const b = fingerprints({ error: "boom", errorStack: "ValueError: boom", sourceTopic: "t2" });
    expect(a.fingerprint).not.toBe(b.fingerprint);
    expect(a.errorFingerprint).toBe(b.errorFingerprint);
  });

  it("matches the pinned fingerprint recipe byte for byte", () => {
    // Golden vectors: the stamped fingerprint is persisted on every document,
    // so a drift in the recipe would split one error into two groups depending
    // on when the document was stamped.
    const out = fingerprints({
      error: "Cargo file 4a1f8e2c-1111-2222-3333-444455556666 not found",
      errorStack: "CargoFileNotFoundError: missing",
      sourceTopic: "cargo-lexical.files",
    });
    expect(out.errorNormalized).toBe("Cargo file <id> not found");
    expect(out.fingerprint).toBe("fp:862306a14d164ae54b03abb1d9e2166b90e429eb");
    expect(out.errorFingerprint).toBe("efp:51f249a101dbcc4565a5260eb7536745f743f0d1");
    // Bump this and `ensureStamped` re-derives the whole collection — which is
    // the only safe way to change anything above.
    expect(out.fpVersion).toBe(4);
  });

  it("keeps the two namespaces apart", () => {
    const out = fingerprints({ error: "boom", errorStack: "ValueError: boom", sourceTopic: "t" });
    expect(out.fingerprint.startsWith("fp:")).toBe(true);
    expect(out.errorFingerprint.startsWith("efp:")).toBe(true);
  });
});
