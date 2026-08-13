import { NextResponse } from "next/server";

import { config } from "@/lib/config";

export const dynamic = "force-dynamic";

/**
 * The two values the browser needs to build its own authorize redirect.
 *
 * Served rather than baked in at build time because the image is built once and
 * configured per cluster — a `NEXT_PUBLIC_` var would freeze whatever
 * `next build` happened to see. Nothing secret is reachable here: the client
 * secret lives in `config.auth`, and the browser is a public client's worth of
 * information short of it by design.
 */
export function GET() {
  return NextResponse.json(config.publicAuth);
}
