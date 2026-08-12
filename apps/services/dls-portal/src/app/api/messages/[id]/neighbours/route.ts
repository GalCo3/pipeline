import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { neighbours } from "@/server/repository/messages";

export const dynamic = "force-dynamic";

/**
 * Prev/next within an error group — what makes the message screen a serial
 * review loop instead of a dead end. Needs `?fingerprint=`; `?status=` keeps the
 * walk inside the filter the operator was looking at.
 */
export const GET = route(async (request: Request, ctx: { params: Promise<{ id: string }> }) => {
  await requireSession();
  const { id } = await ctx.params;
  const url = new URL(request.url);
  const fingerprint = url.searchParams.get("fingerprint");
  if (!fingerprint) return NextResponse.json({ prev: null, next: null });
  return NextResponse.json(await neighbours(id, fingerprint, url.searchParams.get("status")));
});
