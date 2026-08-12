import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { groupsInTopic } from "@/server/repository/groups";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/** Error groups within one source topic, keyed on the topic-scoped fingerprint. */
export const GET = route(
  async (_request: Request, ctx: { params: Promise<{ sourceTopic: string }> }) => {
    await requireSession();
    await ensureStamped();
    const { sourceTopic } = await ctx.params;
    return NextResponse.json(await groupsInTopic(decodeURIComponent(sourceTopic)));
  },
);
