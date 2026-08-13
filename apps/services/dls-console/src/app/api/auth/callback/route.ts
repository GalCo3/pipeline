import { NextResponse } from "next/server";

import { body, route } from "@/app/api/_lib/handler";
import { ActionError } from "@/lib/errors";
import { actorFromClaims, exchangeCode, verifyAccessToken } from "@/lib/oidc";
import { sessionFrom, writeSessionCookie } from "@/lib/session";

export const dynamic = "force-dynamic";

type Input = { code: string; redirectUri: string };

/**
 * Exchange the browser's authorization code for a session.
 *
 * Unauthenticated by necessity — it runs before a session exists, and it is one
 * of the only routes without `requireActor`. It mints no trust of its own: the
 * token it stores is one the IdP issued, and it is validated against JWKS here
 * before the cookie is written, so a code that buys an unusable token fails at
 * sign-in rather than on the first action.
 *
 * `redirectUri` comes from the browser because the browser is what sent it to
 * the authorize endpoint; Keycloak compares the two byte for byte and answers
 * `invalid_grant` on any difference. It is not a trust decision — the IdP only
 * accepts URIs already registered on the client.
 */
export const POST = route(async (request: Request) => {
  const input = await body<Input>(request);
  if (!input.code || !input.redirectUri) {
    throw new ActionError(400, "code and redirectUri are required");
  }

  const tokens = await exchangeCode(input.code, input.redirectUri);

  let actor: string | null;
  try {
    actor = actorFromClaims(await verifyAccessToken(tokens.accessToken));
  } catch (cause) {
    // The IdP issued it and we still cannot verify it: wrong issuer, wrong
    // audience, or a JWKS this pod cannot fetch. All are deploy-side.
    throw new ActionError(502, `token failed validation: ${String(cause)}`);
  }
  if (!actor) throw new ActionError(502, "token carries no usable identity claim");

  const session = sessionFrom(tokens, actor, null);
  await writeSessionCookie(session);
  return NextResponse.json({ actor, expiresAt: session.expiresAt });
});
