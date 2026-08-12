import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { ensureStamped } from "@/server/repository/stamp";
import { stats } from "@/server/repository/stats";

export const dynamic = "force-dynamic";

/** Dashboard stats: totals by status, top error groups, topic count. */
export const GET = route(async () => {
  await requireSession();
  await ensureStamped();
  return NextResponse.json(await stats());
});
