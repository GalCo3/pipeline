import "server-only";

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";

import { config } from "@/lib/config";
import { ActionError, upstreamFailed } from "@/lib/errors";

/**
 * OIDC Authorization Code, confidential client — the server's half.
 *
 * The SSO issues confidential clients only, so the browser can do neither PKCE
 * nor its own token exchange: a public/PKCE client is rejected at the authorize
 * endpoint, and the token endpoint demands `client_id` + `client_secret`. The
 * browser therefore drives only the *redirect* leg (see
 * `src/lib/auth/browser.ts`) and hands the authorization code to this process,
 * which holds the secret. That is the same split dlq-triage runs, and the
 * reason this file exists instead of an off-the-shelf provider: next-auth,
 * oidc-client-ts and friends all assume they own the exchange, and all of them
 * send a `code_challenge` the realm answers with 400.
 *
 * No discovery either. Every endpoint is built from the bare realm URL, because
 * Keycloak fills its discovery document from `KC_HOSTNAME` — pointing discovery
 * at an internal host still hands back the public token endpoint, which this
 * pod cannot reach.
 *
 * Split horizon: `issuerUrl` is what the *browser* reaches and what the token's
 * `iss` claim carries; `idpBase` is what this process reaches. They differ
 * wherever the SSO is not routable from inside the cluster.
 *
 * TLS: the SSO is signed by an internal CA and node ships its own trust store,
 * so `NODE_EXTRA_CA_CERTS` must point at the bundle. It is read once at process
 * start and applies to both hops below — the token POST and the JWKS fetch —
 * which is why there is no per-call CA option here.
 */

const TIMEOUT_MS = 10_000;

function endpoint(base: string, path: string): string {
  return `${base.replace(/\/$/, "")}/protocol/openid-connect/${path}`;
}

/** Browser-facing authorize endpoint. Only the browser ever calls this. */
export function authorizeEndpoint(): string {
  return endpoint(config.auth.issuerUrl, "auth");
}

/** Browser-facing end-session endpoint. */
export function logoutEndpoint(): string {
  return endpoint(config.auth.issuerUrl, "logout");
}

export interface TokenSet {
  accessToken: string;
  expiresIn: number;
  refreshToken: string | null;
  idToken: string | null;
}

function tokenSet(raw: Record<string, unknown>): TokenSet {
  return {
    accessToken: String(raw.access_token),
    expiresIn: Number(raw.expires_in ?? 300),
    refreshToken: raw.refresh_token ? String(raw.refresh_token) : null,
    idToken: raw.id_token ? String(raw.id_token) : null,
  };
}

/**
 * Surface the IdP's own reason (`invalid_grant`, `invalid_client`, …) — it is
 * the only thing that makes these failures diagnosable, and it is safe to
 * relay: the IdP's error body never echoes the secret back.
 */
async function reason(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const body = JSON.parse(text) as { error_description?: string; error?: string };
    return body.error_description ?? body.error ?? "token request failed";
  } catch {
    return text.slice(0, 200) || "token request failed";
  }
}

async function post(form: Record<string, string>): Promise<TokenSet> {
  const { clientId, clientSecret } = config.auth;
  if (!clientSecret) {
    // Misconfiguration, not a client error: the deploy is missing its Secret.
    throw new ActionError(503, "OIDC client secret is not configured");
  }
  const body = new URLSearchParams({ ...form, client_id: clientId, client_secret: clientSecret });

  let response: Response;
  try {
    response = await fetch(endpoint(config.auth.idpBase, "token"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      signal: AbortSignal.timeout(TIMEOUT_MS),
      // The token endpoint's answer is single-use by definition; Next's fetch
      // cache would be actively wrong here.
      cache: "no-store",
    });
  } catch (cause) {
    throw upstreamFailed(`identity provider unreachable: ${String(cause)}`);
  }
  if (!response.ok) {
    throw new ActionError(response.status, await reason(response));
  }
  return tokenSet((await response.json()) as Record<string, unknown>);
}

/** Authorization code -> token set. `redirectUri` must byte-match the one the
 *  browser sent to the authorize endpoint, or Keycloak answers `invalid_grant`. */
export function exchangeCode(code: string, redirectUri: string): Promise<TokenSet> {
  return post({ grant_type: "authorization_code", code, redirect_uri: redirectUri });
}

/** Refresh token -> a fresh token set. Access tokens live ~5 minutes. */
export function refreshTokens(refreshToken: string): Promise<TokenSet> {
  return post({ grant_type: "refresh_token", refresh_token: refreshToken });
}

/**
 * JWKS, cached across requests.
 *
 * `createRemoteJWKSet` holds its own key cache and refetches on an unknown
 * `kid`, so this is built once per process rather than per request — the
 * alternative is a JWKS round trip on every API call.
 */
let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function keySet(): ReturnType<typeof createRemoteJWKSet> {
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(endpoint(config.auth.idpBase, "certs")), {
      cacheMaxAge: config.auth.jwksTtl * 1000,
    });
  }
  return jwks;
}

/**
 * Validate an access token and return its claims.
 *
 * `iss` is checked against the *browser-facing* issuer — that is what the token
 * carries — while the keys come from `idpBase`. Audience is checked only when
 * `AUTH_OIDC_AUDIENCE` is set: Keycloak's default access token carries
 * `aud: account`, so demanding the client id here would reject every token
 * until the realm has an audience mapper. Set it once the mapper exists; leave
 * it unset and this validates issuer, signature and expiry only.
 */
export async function verifyAccessToken(token: string): Promise<JWTPayload> {
  const { audience } = config.auth;
  const { payload } = await jwtVerify(token, keySet(), {
    issuer: config.auth.issuerUrl.replace(/\/$/, ""),
    ...(audience ? { audience } : {}),
    algorithms: ["RS256"],
    requiredClaims: ["exp", "iss"],
  });
  return payload;
}

/** preferred_username -> email -> sub. The audit actor, from claims only. */
export function actorFromClaims(claims: JWTPayload): string | null {
  const preferred = claims.preferred_username;
  const email = claims.email;
  if (typeof preferred === "string" && preferred) return preferred;
  if (typeof email === "string" && email) return email;
  return typeof claims.sub === "string" ? claims.sub : null;
}
