import { NextResponse } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import { requireActor } from "@/server/auth";
import { discard } from "@/server/actions/discard";

export const dynamic = "force-dynamic";

/** Soft-delete. The document survives; only its triage state changes. */
export const POST = route(async (request: Request, ctx: { params: Promise<{ id: string }> }) => {
  const actor = await requireActor();
  const { id } = await ctx.params;
  const input = await body<{ reason?: string }>(request);
  return NextResponse.json(await discard(id, actor, { reason: input.reason ?? null }));
});
