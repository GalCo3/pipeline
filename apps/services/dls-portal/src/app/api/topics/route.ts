import { NextResponse } from "next/server";

import { computeLag } from "@/lib/kafka/admin";
import { route } from "@/app/api/_lib/handler";
import { requireSession } from "@/server/auth";
import { ensureStamped } from "@/server/repository/stamp";
import { topicsSummary } from "@/server/repository/topics";

export const dynamic = "force-dynamic";

/** Overview: one row per source topic that has dead-lettered, plus its lag. */
export const GET = route(async () => {
  await requireSession();
  await ensureStamped();
  const summaries = await topicsSummary();

  // Lag is best-effort and only for the topics on screen — never fail the
  // overview because a broker is slow or a consumer group has never committed.
  const lag: Record<string, number> = await computeLag(
    summaries.map((t) => t.sourceTopic).filter(Boolean),
  ).catch(() => ({}));

  return NextResponse.json(
    summaries.map((topic) => ({ ...topic, lag: lag[topic.sourceTopic] ?? null })),
  );
});
