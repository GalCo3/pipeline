import { NextResponse } from "next/server";

import { ActionError } from "@/lib/errors";

/**
 * Route-handler plumbing: auth, error mapping, pagination.
 *
 * Every route is a thin shell — parse, authorize, call the server layer, render.
 * Orchestration lives under `src/server`, which throws `ActionError` and knows
 * nothing about HTTP.
 */

export function jsonError(error: unknown): NextResponse {
  if (error instanceof ActionError) {
    return NextResponse.json({ detail: error.detail }, { status: error.status });
  }
  console.error("unhandled route error", error);
  return NextResponse.json({ detail: "internal error" }, { status: 500 });
}

/** Wrap a handler so thrown `ActionError`s become their documented status. */
export function route<T extends unknown[]>(
  handler: (...args: T) => Promise<NextResponse>,
): (...args: T) => Promise<NextResponse> {
  return async (...args: T) => {
    try {
      return await handler(...args);
    } catch (error) {
      return jsonError(error);
    }
  };
}

export function pageParams(url: URL): { page: number; pageSize: number } {
  const page = Math.max(1, Number(url.searchParams.get("page") ?? 1) || 1);
  const requested = Number(url.searchParams.get("pageSize") ?? 50) || 50;
  // Capped: a listing is a screen, and an uncapped pageSize is a way to pull the
  // whole dead letter store through one request.
  return { page, pageSize: Math.min(200, Math.max(1, requested)) };
}

export function pageBody<T>(items: T[], total: number, page: number, pageSize: number) {
  return { items, total, page, pageSize };
}

/** JSON body of a request, or `{}` when there is none (actions allow both). */
export async function body<T>(request: Request): Promise<Partial<T>> {
  try {
    return (await request.json()) as Partial<T>;
  } catch {
    return {};
  }
}
