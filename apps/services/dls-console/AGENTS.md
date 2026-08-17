# Agent Guide — DLS Console

Console over the pipeline's dead letter store: makes `hermes.dls` visible,
groupable and actionable (replay / edit & replay / discard). Without it, failed
messages sit in Mongo unread.

One Next.js app — the UI and the API are the same process, the same deployment
and the same image.

```
service consumer fails ──▶ hermes.dls (MongoDB) ──▶ dls-console ──▶ browser
                                                        │
                                                        └──▶ Kafka source topic (replay)
```

## Shape

- **One process.** No nginx `/api` proxy, no `BACKEND_ORIGIN`, no CORS, no
  second chart. The browser calls same-origin `/api` routes.
- **Auth is server-side.** next-auth holds the client secret and does the code
  exchange in-process; the browser gets a session cookie and never an access
  token.
- **Mongo and Kafka keys are the Python services' keys.**
  `MONGO_CONFIG__LOCAL_HOST`, `CONSUMER_CONFIG__BOOTSTRAP_SERVERS`,
  `DLS_COLLECTION` — pydantic-settings spelling, nested with `__`, so one
  cluster's ConfigMap and Secret feed this app and the services alike. Only this
  app's own settings (`AUTH_*`, `LAG_*`, `DEV_*`) are flat, having no Python
  counterpart to agree with.
- **Kafka is `@confluentinc/kafka-javascript`** — the same librdkafka the Python
  services use, so broker TLS and config keys (`ssl.ca.location`, …) carry over
  unchanged.

**Fingerprints are pinned** (a defined normalization, `sha1(parts joined by
\x1f)`, `fp:` / `efp:` prefixes) — but **versioned rather than frozen**: the hash
is persisted, so a recipe change without a matching `FP_VERSION` bump leaves the
collection half-hashed one way and half the other, one error reading as two
groups depending on when its document happened to be stamped. Bump the version
with the recipe and the stamp pass re-derives everything.

## Key invariants — read before coding

- **Mongo is the read path, Kafka the write path.** The console browses, groups
  and counts from `hermes.dls` only. It touches Kafka to produce a replay and to
  read consumer-lag metadata. **It never consumes** — joining a consumer group
  would move the pipeline's own offsets.
- **The DLS document belongs to the pipeline.**
  `libs/utils/src/hermes/utils/dls.py` is the contract; this app may add triage
  fields beside it but never rewrites `original_message`, `source_topic`,
  `partition`, `offset`, `error`, `error_stack` or `failed_at`.
- **Replay goes back to `source_topic`.** The consumer that dropped the message
  is the one that should see it again. No routing table, no target derivation —
  an explicit `targetTopic` is the only redirect.
- **Replay is a plain JSON produce.** Never introduce Schema-Registry
  serialization: the pipeline's topics are plain JSON, and an SR-framed record
  would be undeserializable to every consumer downstream.
- **No key and no original headers exist.** The consumer hands its handler a
  decoded value, so `send_to_dls` stores that and nothing else. A replay may
  *supply* a key and headers from the edit form — they are the operator's, never
  a restoration — and `x-dls-replay-of` is stamped on top of whatever is given.
- **NEW is the absence of `status`.** The services write no status field, and the
  stamp pass deliberately never writes one — a stamp racing an operator's
  discard could otherwise revive a resolved document.
- **Grouping is derived, not ingested.** No sink computes fingerprints, so the
  read path normalizes the error text and stamps `fingerprint` /
  `errorFingerprint` onto documents that lack them. Idempotent and batched.
- **A document is one failure.** Nothing merges repeats, so "seen N times" is the
  count of documents in a group rather than a per-document counter.
- **Discard is a soft-delete.** The one hard-delete is the explicit **Clear
  history** purge, and what it removes are rows the services wrote — hence the
  type-`CLEAR` confirmation and no TTL.
- **Every action writes an audit entry** — success or failure, single or bulk.
  No status change without one.
- **The audit `actor` comes from the session**, never from the request body.
- **Bulk is per-message under the hood** and **async** (`202 + bulkId`, the UI
  polls). Partial failure is normal and reported per message.
- **Nothing server-side is importable from the browser.** `src/lib/config.ts`,
  `src/lib/mongo.ts` and the Kafka modules import `server-only`, so a stray
  client import is a build error rather than a leaked password.

## Data model (MongoDB `hermes`)

`dls` — one document per failure, **written by the services**:

- `original_message` (the decoded value the handler choked on), `source_topic`,
  `partition`, `offset`, `error` (`str(exc)`), `error_stack` (formatted
  traceback), `failed_at`.

Fields this app adds to that same document, never replacing the above:

- **derived identity** (stamped on first read): `errorType`, `errorNormalized`,
  `fingerprint` (`fp:` — topic-scoped), `errorFingerprint` (`efp:` —
  topic-independent), `fpVersion` (the recipe that produced them; a document
  carrying an older one is re-stamped).
- **state** (written by actions): `status` (`REPLAYED | DISCARDED`; absent means
  `NEW`), `resolvedAt`, `resolvedBy`, `edited`, `editedPayload`.

Indexes created on first read: `(fingerprint, status)`,
`(errorFingerprint, status)`, `(source_topic, status)`, `(failed_at)`,
`(resolvedAt)`. None unique — repeats are real data, and their count is what
"seen N times" means.

`audit` — append-only, console-owned: `messageId`, `action`
(`REPLAY | EDIT_REPLAY | DISCARD | CLEAR_HISTORY`), `actor`, `at`, `bulkId`,
`detail`, `result`, `error`. `bulks` — console-owned bulk progress, in Mongo so it
survives a restart.

### State machine

`NEW → REPLAYED` (replay / edit & replay) or `NEW → DISCARDED` (discard); both
terminal and read-only in the UI. Transitions guard on "still NEW" *in the update
filter*, so two concurrent actions cannot both resolve a document — the loser
matches nothing and reports 409.

A replayed message that fails again is written by the service as a **new
document**; it carries `x-dls-replay-of` on the Kafka record, but the DLS record
itself has no back-reference. Re-entry shows up as another member of the same
error group rather than as a reopened document.

### Fingerprinting

From the `error` string only. Normalize (mask the **writing service and its
topic** first, then **brace-delimited payload echoes**, then UUIDs, ISO
timestamps, hex digests, addresses, **opaque alphanumeric ids**, then bare
numbers — in that order, or the number sweep shreds the others), recover the
exception class from the last traceback line,
then hash twice: `fingerprint = sha1(type + normalized + source_topic)` (`fp:`,
drives the topic screen) and `errorFingerprint = sha1(type + normalized)`
(`efp:`, collapses one error spanning N topics into one row). Group lookups and
bulk-by-group match either key.

The writer mask is what makes `efp:` do anything at all here: every service
interpolates its own name into the message (`Failed to index cargo-lexical
document 4`), so without it the same bug in six services is six rows and the "by
error" lens is just the topic lens with the topics hidden. The tokens masked are
taken from the document's `source_topic` — never matched by shape — so a
hyphenated word that merely looks like a slug (`read-only`) survives.

The object mask is the other half of it. A validator prints the object it choked
on (`input_value={'id': 4, 'name': 'bob', …}`), which is unique per document and
makes every group a group of one; the braces mark that span as data rather than
description, so it collapses to `<obj>` and the model, field and constraint
around it stay. On this pipeline's store the two masks together take 24 groups
down to 5.

The opaque-id rule is the third. The ids this pipeline carries look like
`QMdvxJcvT4LzsCS9d` — not a UUID (no dashes), not all-hex (the digest rule misses
it), and immune to the bare-number sweep because letters sit either side of the
digits — so `Failed to index <svc> document QMdvxJcvT4LzsCS9d` hashed one group
per document, which is exactly the "grouping doesn't group" symptom. Any
`[A-Za-z0-9_-]` word of six or more characters carrying at least one letter and
at least one digit becomes `<id>`. It over-reaches onto `base64`/`sha256`/`utf16`
and that is the accepted trade: it costs a little readability in a group title
and nothing in grouping, since the collapse is consistent.

## Layout

```
src/app/               routes — pages and /api handlers (thin: parse, authorize, render)
src/server/            orchestration; throws ActionError, knows nothing about HTTP
  repository/          the only place that knows a Mongo field name
  actions/             replay, discard, bulk, clear-history
src/lib/               config, mongo, kafka, fingerprint, errors, types, browser client
src/components/        UI primitives + screens' shared parts
tests/                 vitest
```

The dependency rule is one-way: `app → server → lib`. A route never touches
Mongo directly, and the repository never returns a snake_case field to anything
above it.

## API (`/api`)

| Method & path | Purpose |
| --- | --- |
| `GET /topics` | Overview: per-source-topic counts by status, distinct error groups, document count, consumer lag, first/last seen |
| `GET /topics/{sourceTopic}/groups` | Error groups in a topic (`fp:`) |
| `GET /groups` | Error groups across every topic (`efp:`) |
| `GET /groups/{fingerprint}/messages` | Messages in a group — paginated, `status`-filterable |
| `GET /messages?sourceTopic=&fingerprint=&status=&q=&page=` | Generic listing |
| `GET /messages/{id}` | Full document: payload, error + stack, partition/offset |
| `GET /messages/{id}/audit` | Audit trail for one message |
| `GET /messages/{id}/neighbours?fingerprint=` | Prev/next within the group — the serial review loop |
| `POST /messages/{id}/replay` | Replay; body `{payload?, targetTopic?, key?, headers?}` — `payload` makes it edit & replay |
| `POST /messages/{id}/discard` | Soft-delete, body `{reason?}` |
| `GET /history`, `DELETE /history` | Resolved messages; Clear-history purge |
| `POST /bulk/replay`, `POST /bulk/discard` | `{target: {fingerprint} \| {sourceTopic} \| {messageIds[]}, edit?/reason?}` → `202 {bulkId}` |
| `POST /bulk/shared` | Synchronous — the shared payload keys a bulk edit may touch |
| `GET /bulk/{bulkId}` | Progress: `{state: RUNNING\|DONE, total, ok, failed, skipped, results[]}` |
| `GET /api/health` | Mongo + Kafka, unauthenticated |
| `GET /api/health/ready` | Dependency-free readiness — what the probes point at |
| `GET /stats` | Dashboard headline: status totals + distinct source-topic count |

Two identities travel on every message shape, and only one is a key: **`id`**
(Mongo `_id`) is what everything keys on; **`kafkaId`** (`"partition:offset"`) is
what an operator pastes into Kafbat to find the original record. There is no
`kafkaKey` — the DLS record keeps no Kafka key. Never key on `kafkaId`.

Bulk work runs via `after()` so it stays attached to the request lifecycle rather
than floating as a detached promise, and `run()` never rejects — an unhandled
rejection in a background task takes the whole node process down.

## Actions

**Replay** — guard NEW; encode the stored `original_message` as JSON; produce it
to the document's `source_topic` (or an explicit `targetTopic`); await the broker
ack; then set `REPLAYED` + audit with `producedOffset`. `acks=all`, because a
document is about to be marked resolved on the strength of that ack.

**Edit & replay** — same path with an edited payload, stored as `editedPayload`
beside the untouched `original_message`.

**Discard** — `status=DISCARDED`, `resolvedAt/By`, audit with the optional
reason. The consumer already committed the offset when it dead-lettered.

**Bulk** — target an error group, a whole topic, or an explicit selection. Only
`NEW` messages are eligible; the rest are skipped and reported. One `bulkId`
stamps every resulting audit entry. Without a redirect each message replays to
**its own** `source_topic`, which matters for a cross-topic error group.

**Bulk edit & replay** is shared-values-only: `POST /bulk/shared` deep-compares
the target's `NEW` payloads and returns the top-level keys identical across all
of them, the varying keys (shown locked) and the common source topic. Past
`SHARED_CAP` (1000) it returns `tooMany` and the payload form falls back to plain
replay-all. Applying an edit: `payload` is a **shallow** merge of top-level keys
(nested objects replaced whole), new keys may be added, and `targetTopic`, `key`
and `headers` apply to the whole batch.

The three record-level fields — **produced to / record key (id) / headers** —
are one component (`components/RecordOverrides.tsx`) shared by the single-message
edit modal and the bulk one, so a replay is described identically whether it is
aimed at one document or a thousand. They are *supplied*, never compared or
restored, which is why `tooMany` doesn't disable them and why the message screen
no longer carries a loose target-topic box beside its buttons.

Failure map: no `source_topic` and no override → 409 · payload not
JSON-encodable → 422 · produce/ack fails → 502, status stays `NEW` · already
resolved → 409 single / skipped in bulk. All of them write a `FAILED` audit
entry.

## UI

Drill-down: **overview → topic or error group → one message + actions**, plus a
**History** screen. The overview has two lenses over the same store because the
operator arrives with one of two questions: "by topic" answers *which service is
bleeding*, "by error" answers *what is actually broken*.

The overview is three tiers and stays three: headline, four counts, one list.
There is deliberately no "most frequent errors" panel beside the list — it
ranked rows the list already held, so it read as a second thing to scan rather
than a shortcut, and the aggregation behind it is gone with it (`/stats` returns
totals and a topic count, nothing more). Type is sized for a wall screen: `Panel`
lists run at body size with mono sub-lines, and the numeric columns are
fixed-width and tabular so counts line up down a list instead of drifting with
the text beside them. Each list carries a column header — the right-hand columns
are icons and dots, fast to scan once known and opaque until then.

The group screen carries the same two bulk entry points as the topic screen:
**Bulk edit & replay** over every NEW member, and per-row checkboxes feeding a
fixed selection bar for a subset. Both open the one bulk modal — a group is a
target like any other, and having to leave the group to bulk-act on it was the
gap.

The message screen's header leads with the **payload's own id**
(`id`/`ID`/`Id`/`iD`/`_id` — case is not agreed across producers), then the Mongo
**`doc`** id the API keys on. Both are labelled: unlabelled, two hex-ish strings
side by side read as the same thing said twice. `partition` / `offset` belong to
the Coordinates panel and the header does not repeat them as a `part:offset`
chip.

Filters default to `NEW` — resolved messages live on History. Status colors are
consistent everywhere (NEW = attention/amber, REPLAYED = success/green,
DISCARDED = muted), and color is never the only signal: each status pairs a glyph
with its hue. Destructive and bulk actions always confirm and always show
per-message results — silent partial failure is a bug. **Discard confirms
twice**: the dialog, then a five-second countdown after the operator commits,
cancellable for as long as it runs. Replay is recoverable — the message goes
back to its topic and re-dead-letters if it fails again — but a discard is a
terminal state with no undo in the UI, so the second gate is where a mis-aimed
one, single or bulk, gets taken back. Nothing is sent until the count reaches
zero.

`components/Footer.tsx` carries the signature line and two easter eggs (the
skull cycles epitaphs, the konami code prints a line). They are inert by
construction — they change text and nothing else, touch no request, no session
and no store — because the worst thing an operator should be able to do by
poking at the footer mid-incident is read a joke. The key handler ignores events
from `INPUT`/`TEXTAREA` so it cannot fire while someone is editing a payload.

## Build & run

Node is **not** installed on the host: this app builds in Docker like everything
else here.

```bash
docker build -f apps/services/dls-console/Dockerfile -t dls-console:local .   # from the repo root
tools/scripts/sandbox/build-images.sh                                               # builds every stack image, records tags
tools/scripts/sandbox/install.sh                                                    # installs the whole stack from those tags
tools/scripts/sandbox/port-forward.sh                                               # console on http://localhost:8086
```

The Dockerfile builds from the **repo root** as context, like every other app
here, and CI picks it up automatically (`tools/ci/find_build.py` treats any
directory under `apps/<group>/` with its own `Dockerfile` as an app).

Two deployment notes worth keeping:

- **8086 is not free-choice.** next-auth posts back to a fixed callback path
  under `AUTH_URL`, so the chart's `AUTH_URL`, the port-forward, and the realm's
  `redirectUris` all have to agree. A mismatch fails login with
  `invalid_redirect_uri`.
- **The IdP's CA must be pointed at, not just mounted.** Node ships its own trust
  store, so an internal-CA SSO needs `NODE_EXTRA_CA_CERTS`.
- **Three separate trust paths, and they do not substitute for each other.**
  `NODE_EXTRA_CA_CERTS` is the IdP's TLS only. Mongo reads
  `MONGO_CONFIG__AUTH__LOCAL__CA_PATH` / `__CERT_PATH` (one PEM with the key
  concatenated, as pymongo takes it) and optionally `__KEY_PATH` when the key is
  a separate file; Kafka reads its own `CONSUMER_CONFIG__SSL__*` triple, where
  the key is always separate. Setting the wrong one fails as a certificate error
  that names the right file.

`.env.example` is the source of truth for configuration. Against the local
Keycloak: realm `dls-console`, client `dls-console` with secret
`dev-console-secret`, user `dev` / `dev`.
