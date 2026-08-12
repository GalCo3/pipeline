import { NextResponse } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import type { BulkTarget } from "@/lib/types";
import { requireSession } from "@/server/auth";
import { computeShared } from "@/server/repository/bulk";

export const dynamic = "force-dynamic";

/**
 * The shared payload keys a bulk edit may touch. Synchronous — the modal needs
 * the answer before it can render a form.
 */
export const POST = route(async (request: Request) => {
  await requireSession();
  const input = await body<{ target: BulkTarget }>(request);
  return NextResponse.json(await computeShared(input.target ?? {}));
});
