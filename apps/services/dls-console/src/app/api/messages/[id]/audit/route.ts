import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { auditFor } from "@/server/repository/audit";

export const dynamic = "force-dynamic";

/** Audit trail for one message — every action, including the failed ones. */
export const GET = route(async (_request: Request, ctx: { params: Promise<{ id: string }> }) => {
  await requireSession();
  const { id } = await ctx.params;
  const entries = await auditFor(id);
  if (entries === null) return NextResponse.json({ detail: "message not found" }, { status: 404 });
  return NextResponse.json(entries);
});
