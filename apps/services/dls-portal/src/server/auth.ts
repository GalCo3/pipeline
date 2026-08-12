import "server-only";

import { auth } from "@/auth";
import { config } from "@/lib/config";
import { unauthorized } from "@/lib/errors";

/**
 * The actor every audit entry is attributed to.
 *
 * It comes from the session the IdP issued — `preferred_username` → `email` →
 * `sub` — and never from the request body: an operator must not be able to name
 * someone else as the person who replayed a message.
 */
export async function requireActor(): Promise<string> {
  // Dev bypass exists so the portal runs against a local Mongo without a
  // Keycloak in the loop. It is off by default and must stay off anywhere real.
  if (config.auth.devBypass) return config.auth.devActor;

  const session = await auth();
  const actor = session?.user?.email ?? session?.user?.name;
  if (!actor) throw unauthorized();
  return actor;
}

/** Read-only routes: same check, no actor needed. */
export async function requireSession(): Promise<void> {
  await requireActor();
}
