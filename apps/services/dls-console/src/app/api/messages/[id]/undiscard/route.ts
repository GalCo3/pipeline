import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireActor } from "@/server/auth";
import { undiscard } from "@/server/actions/discard";

export const dynamic = "force-dynamic";

/** Reverses a discard: DISCARDED -> NEW, back in the operator's queue. */
export const POST = route(async (_request: Request, ctx: { params: Promise<{ id: string }> }) => {
  const actor = await requireActor();
  const { id } = await ctx.params;
  return NextResponse.json(await undiscard(id, actor));
});
