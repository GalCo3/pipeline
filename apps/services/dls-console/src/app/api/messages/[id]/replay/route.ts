import { NextResponse } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import type { ReplayInput } from "@/lib/types";
import { requireActor } from "@/server/auth";
import { replay } from "@/server/actions/replay";

export const dynamic = "force-dynamic";

/**
 * Replay, or edit & replay when `payload` is present.
 *
 * Empty body is the normal case: the message goes back to the `source_topic` it
 * failed on, because the consumer that dead-lettered it is the one that should
 * see it again. `targetTopic` is the only redirect, and `key` / `headers` are
 * operator-supplied — the DLS document kept neither.
 */
export const POST = route(async (request: Request, ctx: { params: Promise<{ id: string }> }) => {
  const actor = await requireActor();
  const { id } = await ctx.params;
  const input = await body<ReplayInput>(request);
  return NextResponse.json(
    await replay(id, actor, {
      payload: input.payload ?? null,
      targetTopic: input.targetTopic,
      key: input.key,
      headers: input.headers,
    }),
  );
});
