import { NextResponse } from "next/server";

import { ping as kafkaPing } from "@/lib/kafka/admin";
import { ping as mongoPing } from "@/lib/mongo";

export const dynamic = "force-dynamic";

/**
 * Liveness — unauthenticated, since a probe has no session.
 *
 * Reports per-dependency state rather than failing outright: Kafka being down
 * means replays fail, but browsing the store still works, and a probe that
 * killed the pod for it would take the read path away too. Kubernetes probes
 * should point at `/api/health/ready`.
 */
export async function GET() {
  const checks = {
    mongo: await mongoPing().then(
      () => "ok" as const,
      () => "down" as const,
    ),
    kafka: await kafkaPing().then(
      () => "ok" as const,
      () => "down" as const,
    ),
  };
  const ok = Object.values(checks).every((v) => v === "ok");
  return NextResponse.json({ status: ok ? "ok" : "degraded", checks });
}
