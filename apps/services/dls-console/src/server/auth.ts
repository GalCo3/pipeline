import "server-only";

import { config } from "@/lib/config";
import { unauthorized } from "@/lib/errors";
import { actorFromClaims, verifyAccessToken } from "@/lib/oidc";
import { readSession } from "@/lib/session";

/**
 * The actor every audit entry is attributed to.
 *
 * It comes from the claims of the token the IdP issued — `preferred_username` →
 * `email` → `sub` — and never from the request body: an operator must not be
 * able to name someone else as the person who replayed a message.
 *
 * The token is re-validated against JWKS on every call rather than trusted
 * because it arrived in our own cookie. The cookie proves this process sealed
 * it; it does not prove the token inside is still live, and the session cookie
 * outlives its access token by design. JWKS is cached in-process, so this costs
 * a signature check, not a round trip.
 */
export async function requireActor(): Promise<string> {
  // Dev bypass exists so the console runs against a local Mongo without an IdP
  // in the loop. It is off by default and must stay off anywhere real.
  if (config.auth.devBypass) return config.auth.devActor;

  const session = await readSession();
  if (!session) throw unauthorized();

  let actor: string | null;
  try {
    actor = actorFromClaims(await verifyAccessToken(session.accessToken));
  } catch {
    // Expired, or no longer verifiable. 401 is the honest answer — the browser
    // refreshes on it and retries.
    throw unauthorized();
  }
  if (!actor) throw unauthorized();
  return actor;
}

/** Read-only routes: same check, no actor needed. */
export async function requireSession(): Promise<void> {
  await requireActor();
}
