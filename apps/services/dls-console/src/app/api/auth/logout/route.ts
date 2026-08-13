import { NextResponse } from "next/server";

import { route } from "@/app/api/_lib/handler";
import { logoutEndpoint } from "@/lib/oidc";
import { clearSessionCookie, readSession } from "@/lib/session";

export const dynamic = "force-dynamic";

type Input = { postLogoutRedirectUri?: string };

/**
 * Drop the local session and hand back the IdP's end-session URL.
 *
 * Two halves, and both are needed: clearing the cookie ends the session here,
 * while the SSO session survives it — without the redirect the next sign-in is
 * silently re-authenticated and "log out" looks broken.
 *
 * `id_token_hint` is read from the session server-side rather than accepted
 * from the caller, so a logout cannot be pointed at someone else's token.
 */
export const POST = route(async (request: Request) => {
  const session = await readSession();
  await clearSessionCookie();

  const origin = new URL(request.url).origin;
  let input: Input = {};
  try {
    input = (await request.json()) as Input;
  } catch {
    /* no body is fine — fall back to this origin */
  }

  const params = new URLSearchParams({
    post_logout_redirect_uri: input.postLogoutRedirectUri ?? `${origin}/`,
  });
  if (session?.idToken) params.set("id_token_hint", session.idToken);

  return NextResponse.json({ logoutUrl: `${logoutEndpoint()}?${params.toString()}` });
});
