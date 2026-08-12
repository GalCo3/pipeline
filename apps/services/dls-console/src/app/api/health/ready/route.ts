import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Readiness — proves only that the server is answering.
 *
 * Deliberately dependency-free. A readiness probe that pings Kafka would pull
 * the pod out of its Service whenever a broker blinks, even though the console's
 * read path is Mongo-only and stays perfectly usable. Use `/api/health` for the
 * dependency picture.
 */
export function GET() {
  return NextResponse.json({ status: "ok" });
}
