import { NextResponse } from "next/server";

import { pageBody, pageParams, route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { listMessages } from "@/server/repository/messages";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/** Generic listing: ?sourceTopic=&fingerprint=&status=&q=&page=&pageSize= */
export const GET = route(async (request: Request) => {
  await requireSession();
  await ensureStamped();
  const url = new URL(request.url);
  const { page, pageSize } = pageParams(url);
  const { items, total } = await listMessages({
    sourceTopic: url.searchParams.get("sourceTopic"),
    fingerprint: url.searchParams.get("fingerprint"),
    status: url.searchParams.get("status"),
    q: url.searchParams.get("q"),
    page,
    pageSize,
  });
  return NextResponse.json(pageBody(items, total, page, pageSize));
});
