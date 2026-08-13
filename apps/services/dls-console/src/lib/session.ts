import "server-only";

import { createHash } from "node:crypto";
import { cookies } from "next/headers";
import { EncryptJWT, jwtDecrypt } from "jose";

import { config } from "@/lib/config";
import type { TokenSet } from "@/lib/oidc";

/**
 * The signed-in session, as an encrypted cookie.
 *
 * dlq-triage's SPA keeps its token set in `localStorage` because its backend is
 * a separate origin and every call carries a bearer header. This app is one
 * process serving both the pages and the API, so the tokens never need to be in
 * the browser at all — they live in an httpOnly cookie the browser cannot read,
 * and the server pulls them straight back out on each request. Same flow, one
 * fewer place for an access token to sit.
 *
 * Encrypted rather than signed: the cookie holds the IdP's tokens, and a signed
 * cookie is still a readable one. `dir` + A256GCM, keyed off AUTH_SECRET.
 */

const COOKIE = "dls-console.session";

export interface Session {
  actor: string;
  accessToken: string;
  refreshToken: string | null;
  idToken: string | null;
  /** Epoch ms at which the access token expires. */
  expiresAt: number;
}

/**
 * AUTH_SECRET -> a 32-byte key. SHA-256 rather than a plain byte cast so any
 * secret length works, but it stretches, it does not create: the key is only as
 * strong as the secret, so AUTH_SECRET must be real entropy
 * (`openssl rand -base64 32`), not a memorable word.
 */
function key(): Uint8Array {
  return new Uint8Array(createHash("sha256").update(config.auth.sessionSecret).digest());
}

export async function sealSession(session: Session): Promise<string> {
  return new EncryptJWT({ ...session })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    // The cookie outlives the access token on purpose — the refresh token is
    // what keeps the session alive, and an expired access token is a refresh,
    // not a logout.
    .setExpirationTime("12h")
    .encrypt(key());
}

export async function readSession(): Promise<Session | null> {
  const raw = (await cookies()).get(COOKIE)?.value;
  if (!raw) return null;
  try {
    const { payload } = await jwtDecrypt(raw, key());
    const session = payload as unknown as Session;
    return session.accessToken ? session : null;
  } catch {
    // Tampered, expired, or sealed with a previous AUTH_SECRET. All three mean
    // the same thing to the caller: no session.
    return null;
  }
}

/** Session shape for a token set the IdP just issued. */
export function sessionFrom(tokens: TokenSet, actor: string, previous: Session | null): Session {
  return {
    actor,
    accessToken: tokens.accessToken,
    // A refresh response may omit these; keep what we had rather than lose the
    // ability to refresh again.
    refreshToken: tokens.refreshToken ?? previous?.refreshToken ?? null,
    idToken: tokens.idToken ?? previous?.idToken ?? null,
    expiresAt: Date.now() + tokens.expiresIn * 1000,
  };
}

export async function writeSessionCookie(session: Session): Promise<void> {
  (await cookies()).set(COOKIE, await sealSession(session), {
    httpOnly: true,
    // The console is served over HTTPS everywhere it is deployed; `next dev`
    // over plain http is the one case that needs the flag off.
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 12 * 60 * 60,
  });
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(COOKIE);
}
