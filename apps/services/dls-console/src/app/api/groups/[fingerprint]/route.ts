import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { groupByKey } from "@/server/repository/groups";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/**
 * One error group's summary — what the group screen puts in its header.
 *
 * Same either-namespace key as the messages route beside it. 404 when the key
 * matches nothing: an unknown fingerprint is a bad URL, not an empty group.
 */
export const GET = route(
  async (_request: Request, ctx: { params: Promise<{ fingerprint: string }> }) => {
    await requireSession();
    await ensureStamped();
    const { fingerprint } = await ctx.params;
    const group = await groupByKey(decodeURIComponent(fingerprint));
    if (!group) return NextResponse.json({ detail: "group not found" }, { status: 404 });
    return NextResponse.json(group);
  },
);
