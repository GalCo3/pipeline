"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import {
  authorizeUrl,
  consumeState,
  redirectUri,
  stripAuthParams,
  type PublicAuthConfig,
} from "@/lib/auth/browser";
import { Button, ErrorState, Spinner } from "@/components/ui";

/**
 * The sign-in gate: it holds the session state, runs the OIDC dance, and
 * renders the app only once there is an actor.
 *
 * The whole flow is client-side on purpose. The IdP sends the browser back to
 * the app *root* — `redirect_uri` is `origin + "/"`, because that is what the
 * realms register — so the landing page has to notice `?code=` itself. A
 * server-side callback route would need its own registered URI, which is the
 * thing this environment does not hand out.
 *
 * Everything secret still happens on the server: the code goes to
 * `/api/auth/callback`, which exchanges it with the client secret and seals the
 * tokens into an httpOnly cookie. This component never touches a token.
 */

type Status = "loading" | "authenticated" | "anonymous" | "error";

interface SessionState {
  actor: string | null;
  status: Status;
  error: unknown;
  signIn: () => void;
  signOut: () => void;
}

const Context = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const value = useContext(Context);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

// Access tokens live ~300s. Refresh a minute early so an in-flight request never
// rides an expiring token — reactive refresh-on-401 is visibly flaky at this
// TTL.
const REFRESH_SKEW_MS = 60_000;

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  if (!response.ok) {
    let detail = response.statusText || `request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* fall through to the status line */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function SessionProvider({
  devBypass,
  children,
}: {
  devBypass: boolean;
  children: React.ReactNode;
}) {
  const [actor, setActor] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>(devBypass ? "authenticated" : "loading");
  const [error, setError] = useState<unknown>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  // React 18+ mounts effects twice in dev, and an authorization code is
  // single-use — a second exchange fails with `invalid_grant` and would turn a
  // good sign-in into an error screen.
  const exchanging = useRef(false);

  const signIn = useCallback(() => {
    setStatus("loading");
    void json<PublicAuthConfig>("/api/auth/config")
      .then((auth) => {
        window.location.assign(authorizeUrl(auth));
      })
      .catch((cause) => {
        setError(cause);
        setStatus("error");
      });
  }, []);

  const signOut = useCallback(() => {
    void json<{ logoutUrl: string }>("/api/auth/logout", { method: "POST" })
      .then(({ logoutUrl }) => window.location.assign(logoutUrl))
      .catch((cause) => {
        setError(cause);
        setStatus("error");
      });
  }, []);

  // Sign-in, in three cases: back from the IdP with a code, already holding a
  // session cookie, or neither — in which case the redirect starts.
  useEffect(() => {
    if (devBypass) return;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const idpError = params.get("error");

    if (idpError) {
      // The IdP refused before any code existed — `access_denied`,
      // `invalid_scope`, a disabled account. Show it rather than bouncing back
      // into the same redirect and looping.
      stripAuthParams();
      setError(new Error(params.get("error_description") ?? idpError));
      setStatus("error");
      return;
    }

    if (code) {
      if (exchanging.current) return;
      exchanging.current = true;
      if (!consumeState(params.get("state"))) {
        stripAuthParams();
        setError(new Error("sign-in state did not match — start again"));
        setStatus("error");
        return;
      }
      // Read the redirect URI before stripping: the token exchange has to send
      // the same one the authorize request did.
      const uri = redirectUri();
      stripAuthParams();
      void json<{ actor: string; expiresAt: number }>("/api/auth/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, redirectUri: uri }),
      })
        .then((session) => {
          setActor(session.actor);
          setExpiresAt(session.expiresAt);
          setStatus("authenticated");
        })
        .catch((cause) => {
          setError(cause);
          setStatus("error");
        });
      return;
    }

    void json<{ actor: string | null; expiresAt: number | null }>("/api/auth/session")
      .then((session) => {
        if (session.actor) {
          setActor(session.actor);
          setExpiresAt(session.expiresAt);
          setStatus("authenticated");
        } else {
          setStatus("anonymous");
        }
      })
      .catch((cause) => {
        setError(cause);
        setStatus("error");
      });
  }, [devBypass]);

  // No session and nothing in flight — go get one.
  useEffect(() => {
    if (status === "anonymous") signIn();
  }, [status, signIn]);

  // Keep the access token fresh for as long as the tab is open. A failed
  // refresh is terminal: the server has already dropped the cookie, so the only
  // way forward is a new sign-in.
  useEffect(() => {
    if (status !== "authenticated" || !expiresAt) return;
    const delay = Math.max(0, expiresAt - REFRESH_SKEW_MS - Date.now());
    const timer = setTimeout(() => {
      void json<{ actor: string; expiresAt: number }>("/api/auth/refresh", { method: "POST" })
        .then((session) => {
          setActor(session.actor);
          setExpiresAt(session.expiresAt);
        })
        .catch(() => setStatus("anonymous"));
    }, delay);
    return () => clearTimeout(timer);
  }, [status, expiresAt]);

  if (status === "error") {
    return (
      <Splash>
        <div className="w-full max-w-lg">
          <ErrorState error={error} />
          <Button className="mt-4" onClick={signIn}>
            Retry sign-in
          </Button>
        </div>
      </Splash>
    );
  }

  if (status !== "authenticated") {
    return (
      <Splash>
        <Spinner label="Signing in…" />
      </Splash>
    );
  }

  return (
    <Context.Provider
      value={{ actor: devBypass ? null : actor, status, error, signIn, signOut }}
    >
      {children}
    </Context.Provider>
  );
}

function Splash({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <div className="flex items-center gap-2">
        <span className="pulse-signal h-2 w-2 rounded-full bg-brand" />
        <span className="font-display text-lg font-semibold tracking-tight">DLS Console</span>
      </div>
      {children}
    </div>
  );
}
