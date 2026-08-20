import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * The backlog's default view is NEW-only, but that default lives in the URL
 * rather than as an implicit fallback in the page component: landing on `/`
 * with no `status` param redirects to `?status=NEW` once, so from then on
 * "NEW only" is just the same explicit choice a bookmarked or shared link
 * carries — there is no separate "absent means NEW" rule for the page itself
 * to special-case.
 */
export function middleware(request: NextRequest) {
  if (request.nextUrl.searchParams.has("status")) return NextResponse.next();
  const url = request.nextUrl.clone();
  url.searchParams.set("status", "NEW");
  return NextResponse.redirect(url);
}

export const config = {
  matcher: "/",
};
