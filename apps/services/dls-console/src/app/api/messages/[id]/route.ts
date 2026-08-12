import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { getMessage } from "@/server/repository/messages";

export const dynamic = "force-dynamic";

/** Full document: payload, error + stack, partition/offset, edit state. */
export const GET = route(async (_request: Request, ctx: { params: Promise<{ id: string }> }) => {
  await requireSession();
  const { id } = await ctx.params;
  const message = await getMessage(id);
  if (!message) return NextResponse.json({ detail: "message not found" }, { status: 404 });
  return NextResponse.json(message);
});
