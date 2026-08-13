import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { config } from "@/lib/config";
import { readSession } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Who the browser is signed in as, if anyone.
 *
 * Answers 200 with an actor or 200 with `null` — never 401. This is the gate's
 * *question*, not a protected resource, and a 401 here would be
 * indistinguishable in the client from a genuinely rejected API call.
 *
 * Cookie-level only: it reports the session this process is holding, and the
 * access token inside it is re-validated against JWKS on every route that
 * actually does something (see `src/server/auth.ts`).
 */
export const GET = route(async () => {
  if (config.auth.devBypass) {
    return NextResponse.json({ actor: config.auth.devActor, expiresAt: null });
  }
  const session = await readSession();
  return NextResponse.json(
    session ? { actor: session.actor, expiresAt: session.expiresAt } : { actor: null },
  );
});
