/**
 * OIDC Authorization Code — the browser's half.
 *
 * The browser drives only the redirect leg. It never sees the client secret and
 * never exchanges a code: it hands the code to `/api/auth/callback`, which does
 * that server-side. The SSO issues confidential clients only, so this is not a
 * preference — a public/PKCE client is rejected outright, which is exactly what
 * makes an off-the-shelf provider unusable here. Every one of them sends a
 * `code_challenge`, and the realm answers 400.
 *
 * No PKCE therefore, and `state` is ours to mint and verify: without it, an
 * attacker can feed the app an authorization code from another session.
 */

const STATE_KEY = "dls-console.oidc-state";

export interface PublicAuthConfig {
  issuerUrl: string;
  clientId: string;
}

/** The callback URL. Must byte-match what the token exchange later sends, and
 *  must be registered on the client — the realms register the app root. */
export function redirectUri(): string {
  return window.location.origin + "/";
}

function mintState(): string {
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  const state = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  // sessionStorage, not localStorage: the state means something only to the tab
  // that started the redirect, and must not outlive the browser session.
  window.sessionStorage.setItem(STATE_KEY, state);
  return state;
}

/** Verify the `state` the IdP echoed back, and burn it (single use). */
export function consumeState(returned: string | null): boolean {
  const expected = window.sessionStorage.getItem(STATE_KEY);
  window.sessionStorage.removeItem(STATE_KEY);
  return expected !== null && expected === returned;
}

function endpoint(issuerUrl: string, path: string): string {
  return `${issuerUrl.replace(/\/$/, "")}/protocol/openid-connect/${path}`;
}

export function authorizeUrl(auth: PublicAuthConfig): string {
  const params = new URLSearchParams({
    client_id: auth.clientId,
    response_type: "code",
    scope: "openid profile email",
    redirect_uri: redirectUri(),
    state: mintState(),
  });
  return `${endpoint(auth.issuerUrl, "auth")}?${params.toString()}`;
}

/**
 * Strip `code`/`state`/`session_state`/`iss` from the address bar after a
 * successful exchange, so a reload does not re-post a code the IdP has already
 * burned (`invalid_grant`), and so the code stays out of history and referrers.
 */
export function stripAuthParams(): void {
  const url = new URL(window.location.href);
  let touched = false;
  for (const key of ["code", "state", "session_state", "iss"]) {
    if (url.searchParams.has(key)) {
      url.searchParams.delete(key);
      touched = true;
    }
  }
  if (touched) window.history.replaceState({}, "", url.toString());
}
