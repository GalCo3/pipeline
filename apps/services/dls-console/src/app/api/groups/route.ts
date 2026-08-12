import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { allGroups } from "@/server/repository/groups";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/** Error groups across every topic — the home "by error" grouping (efp:*). */
export const GET = route(async () => {
  await requireSession();
  await ensureStamped();
  return NextResponse.json(await allGroups());
});
