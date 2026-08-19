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

/**
 * Browsers cap a single cookie at 4096 bytes of name plus value, and drop the
 * whole `Set-Cookie` when it does not fit. The sealed session carries three
 * IdP-issued JWTs, and a token with a real group list clears that on its own, so
 * the cookie is written in numbered chunks — `<name>.0`, `<name>.1`, … — and
 * reassembled on read. 3500 leaves room for the name and the attributes.
 */
const CHUNK = 3500;
const MAX_CHUNKS = 16;

function chunkName(index: number): string {
  return `${COOKIE}.${index}`;
}

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
  const jar = await cookies();
  let raw = "";
  for (let i = 0; i < MAX_CHUNKS; i += 1) {
    const part = jar.get(chunkName(i))?.value;
    if (part === undefined) break;
    raw += part;
  }
  // The unchunked name is the fallback so a session sealed by an earlier build
  // survives the deploy rather than logging everyone out.
  if (!raw) raw = jar.get(COOKIE)?.value ?? "";
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
  const sealed = await sealSession(session);
  const parts: string[] = [];
  for (let at = 0; at < sealed.length; at += CHUNK) parts.push(sealed.slice(at, at + CHUNK));
  if (parts.length > MAX_CHUNKS) {
    // Reading back only ever reassembles MAX_CHUNKS, so a session that does not
    // fit must fail loudly here rather than round-trip as a corrupt cookie.
    throw new Error(`session too large for ${MAX_CHUNKS} cookie chunks`);
  }

  const options = {
    httpOnly: true,
    // The console is served over HTTPS everywhere it is deployed; `next dev`
    // over plain http is the one case that needs the flag off.
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: 12 * 60 * 60,
  };

  const jar = await cookies();
  parts.forEach((part, index) => jar.set(chunkName(index), part, options));
  // A shorter session than last time leaves trailing chunks behind, and a stale
  // tail concatenates into garbage. Same for a cookie from the unchunked build.
  if (jar.has(COOKIE)) jar.delete(COOKIE);
  for (let i = parts.length; i < MAX_CHUNKS; i += 1) {
    if (jar.has(chunkName(i))) jar.delete(chunkName(i));
  }
}

export async function clearSessionCookie(): Promise<void> {
  const jar = await cookies();
  jar.delete(COOKIE);
  for (let i = 0; i < MAX_CHUNKS; i += 1) {
    if (jar.has(chunkName(i))) jar.delete(chunkName(i));
  }
}
