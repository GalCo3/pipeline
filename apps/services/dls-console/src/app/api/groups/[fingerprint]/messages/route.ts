import { NextResponse } from "next/server";

import { pageBody, pageParams, route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { listMessages } from "@/server/repository/messages";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/**
 * Messages in a group. The path key resolves against either hash namespace
 * (`fp:` topic-scoped or `efp:` cross-topic) — they never collide.
 */
export const GET = route(
  async (request: Request, ctx: { params: Promise<{ fingerprint: string }> }) => {
    await requireSession();
    await ensureStamped();
    const { fingerprint } = await ctx.params;
    const url = new URL(request.url);
    const { page, pageSize } = pageParams(url);
    const { items, total } = await listMessages({
      fingerprint: decodeURIComponent(fingerprint),
      status: url.searchParams.get("status"),
      page,
      pageSize,
    });
    return NextResponse.json(pageBody(items, total, page, pageSize));
  },
);
