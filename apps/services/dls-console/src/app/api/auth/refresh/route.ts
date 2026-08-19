import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { ActionError } from "@/lib/errors";
import { actorFromClaims, refreshTokens, verifyAccessToken } from "@/lib/oidc";
import { clearSessionCookie, readSession, sessionFrom, writeSessionCookie } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Trade the stored refresh token for a fresh token set.
 *
 * Access tokens live ~5 minutes, so the browser calls this on a timer (see
 * `SessionProvider`). Proactive rather than reactive: refresh-on-401 is visibly
 * flaky at that TTL, because a request already in flight rides the token that
 * expires mid-call.
 *
 * The refresh token itself never leaves this process — the browser holds an
 * opaque httpOnly cookie and asks for a renewal, rather than presenting one.
 */
export const POST = route(async () => {
  const current = await readSession();
  if (!current?.refreshToken) {
    throw new ActionError(401, "session expired");
  }

  let tokens;
  try {
    tokens = await refreshTokens(current.refreshToken);
  } catch (error) {
    // A rejected refresh token is terminal — drop the session so the app falls
    // back to a fresh sign-in rather than looping on a dead token.
    await clearSessionCookie();
    throw error;
  }

  const actor = actorFromClaims(await verifyAccessToken(tokens.accessToken)) ?? current.actor;
  const session = sessionFrom(tokens, actor, current);
  await writeSessionCookie(session);
  return NextResponse.json({ actor, expiresAt: session.expiresAt });
});
