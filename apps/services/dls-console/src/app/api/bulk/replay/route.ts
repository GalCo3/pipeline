import { NextResponse } from "next/server";
import { after } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import type { BulkEdit, BulkTarget } from "@/lib/types";
import { requireActor } from "@/server/auth";
import { run, start } from "@/server/actions/bulk";

export const dynamic = "force-dynamic";

type Input = { target: BulkTarget; edit?: BulkEdit | null };

/**
 * Replay every NEW message in a group, a topic, or an explicit selection.
 *
 * Returns `202 {bulkId}` and runs the work after the response via `after()`,
 * which keeps the task attached to the request lifecycle instead of floating as
 * a detached promise. The UI polls `GET /api/bulk/{bulkId}` for live progress.
 *
 * Without a redirect each message replays to **its own** `source_topic`, which
 * is what matters for a cross-topic error group.
 */
export const POST = route(async (request: Request) => {
  const actor = await requireActor();
  const input = await body<Input>(request);
  const target = input.target ?? {};

  // A no-op edit (nothing changed, no redirect, no key or headers) degrades to a
  // plain replay-all — the modal always submits an edit object, so "the operator
  // opened the form and typed nothing" has to be recognized here.
  const touched =
    Boolean(input.edit) &&
    (Object.keys(input.edit?.payload ?? {}).length > 0 ||
      Boolean(input.edit?.targetTopic) ||
      Boolean(input.edit?.key) ||
      Object.keys(input.edit?.headers ?? {}).length > 0);
  const edit = touched ? input.edit : null;

  const { bulkId, messageIds } = await start({ action: "REPLAY", actor, target });
  after(() => run({ bulkId, action: "REPLAY", actor, messageIds, edit }));
  return NextResponse.json({ bulkId, total: messageIds.length }, { status: 202 });
});
