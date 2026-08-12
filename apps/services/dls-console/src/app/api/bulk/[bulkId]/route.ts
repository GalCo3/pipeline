import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { getBulk } from "@/server/repository/bulk";

export const dynamic = "force-dynamic";

/**
 * Live bulk progress. Backed by Mongo, not memory, so it survives a restart and
 * a reload — and stays joinable to the audit ledger through the same `bulkId`.
 */
export const GET = route(
  async (_request: Request, ctx: { params: Promise<{ bulkId: string }> }) => {
    await requireSession();
    const { bulkId } = await ctx.params;
    const bulk = await getBulk(bulkId);
    if (!bulk) return NextResponse.json({ detail: "bulk not found" }, { status: 404 });
    return NextResponse.json(bulk);
  },
);
