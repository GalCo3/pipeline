import { NextResponse } from "next/server";

import { pageBody, pageParams, route } from "@/app/api/_lib/handler";
import { requireActor, requireSession } from "@/server/auth";
import { clearHistory } from "@/server/actions/history";
import { listHistory } from "@/server/repository/history";

export const dynamic = "force-dynamic";

/** Resolved messages, newest-resolved first. */
export const GET = route(async (request: Request) => {
  await requireSession();
  const { page, pageSize } = pageParams(new URL(request.url));
  const { items, total } = await listHistory(page, pageSize);
  return NextResponse.json(pageBody(items, total, page, pageSize));
});

/**
 * Purge every resolved message. The one hard-delete in the system, and what it
 * removes are rows the pipeline's own services wrote — so it stays behind the
 * UI's type-CLEAR confirmation and never runs on a timer.
 */
export const DELETE = route(async () => {
  const actor = await requireActor();
  return NextResponse.json(await clearHistory(actor));
});
