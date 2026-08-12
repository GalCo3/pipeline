import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Session gate for the UI pages.
 *
 * Only pages: the `/api` routes check the session themselves (each one knows
 * whether it needs an actor or just a reader), and they must answer 401 as JSON
 * rather than redirect an XHR into an HTML login page. `/api/health*` stays open
 * for probes.
 *
 * This is a cookie *presence* check, not a validation — middleware runs on the
 * edge runtime where the auth secret's crypto is awkward, and the real check
 * happens in the route/page handlers. Its job is to send a browser without a
 * session to the login screen instead of an empty dashboard.
 */
export function middleware(request: NextRequest) {
  if (process.env.DEV_BYPASS === "true") return NextResponse.next();

  const hasSession =
    request.cookies.has("authjs.session-token") ||
    request.cookies.has("__Secure-authjs.session-token");
  if (hasSession) return NextResponse.next();

  const login = new URL("/api/auth/signin", request.url);
  login.searchParams.set("callbackUrl", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
