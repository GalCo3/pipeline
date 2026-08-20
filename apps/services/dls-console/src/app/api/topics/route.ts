import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { ensureStamped } from "@/server/repository/stamp";
import { topicsSummary } from "@/server/repository/topics";

export const dynamic = "force-dynamic";

/** Overview: one row per source topic that has dead-lettered. */
export const GET = route(async () => {
  await requireSession();
  await ensureStamped();
  return NextResponse.json(await topicsSummary());
});
