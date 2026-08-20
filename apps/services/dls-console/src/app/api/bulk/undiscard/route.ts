import { NextResponse } from "next/server";
import { after } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import type { BulkTarget } from "@/lib/types";
import { requireActor } from "@/server/auth";
import { run, start } from "@/server/actions/bulk";

export const dynamic = "force-dynamic";

type Input = { target: BulkTarget };

/** Undiscard every DISCARDED message in the target. Same ticket + polling as discard. */
export const POST = route(async (request: Request) => {
  const actor = await requireActor();
  const input = await body<Input>(request);
  const { bulkId, messageIds } = await start({
    action: "UNDISCARD",
    actor,
    target: input.target ?? {},
  });
  after(() => run({ bulkId, action: "UNDISCARD", actor, messageIds }));
  return NextResponse.json({ bulkId, total: messageIds.length }, { status: 202 });
});
