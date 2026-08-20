import { NextResponse } from "next/server";

import { pageBody, pageParams, route } from "@/app/api/_lib/handler";
import { MESSAGE_SORT_KEYS, type MessageFilterItem, type MessageFilterModel, type MessageSort } from "@/lib/types";
import { requireSession } from "@/server/auth";
import { listMessages } from "@/server/repository/messages";
import { ensureStamped } from "@/server/repository/stamp";

export const dynamic = "force-dynamic";

/** Comma-separated multi-value param, e.g. `?status=NEW,DISCARDED`. */
function multi(url: URL, name: string): string[] | null {
  const raw = url.searchParams.get(name);
  return raw ? raw.split(",").filter(Boolean) : null;
}

/** `?sortBy=` against an allowlist — an unrecognized or missing key falls back to the default sort. */
function sortParam(url: URL): MessageSort | null {
  const key = url.searchParams.get("sortBy");
  if (!key || !(MESSAGE_SORT_KEYS as readonly string[]).includes(key)) return null;
  const dir = url.searchParams.get("sortDir") === "asc" ? "asc" : "desc";
  return { key: key as MessageSort["key"], dir };
}

const SORT_KEYS = MESSAGE_SORT_KEYS as readonly string[];
// The filter allowlist is one wider than the sort allowlist: `status` is
// filterable (History's own column) but isn't a sort key.
const FILTER_FIELDS: readonly string[] = [...SORT_KEYS, "status"];

/**
 * `?filter=` — the message grid's own per-column filter model, JSON-encoded.
 * Each item is checked against the filterable-column allowlist before it ever
 * reaches the repository; an item with an unknown field, a missing operator,
 * or the wrong shape is dropped rather than rejecting the whole request —
 * one stale filter chip in the URL shouldn't 400 the entire listing.
 */
function filterParam(url: URL): MessageFilterModel | null {
  const raw = url.searchParams.get("filter");
  if (!raw) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || !Array.isArray((parsed as { items?: unknown }).items)) {
    return null;
  }
  const items: MessageFilterItem[] = (parsed as { items: unknown[] }).items
    .filter(
      (item): item is { field: string; operator: string; value?: unknown } =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as { field?: unknown }).field === "string" &&
        typeof (item as { operator?: unknown }).operator === "string" &&
        FILTER_FIELDS.includes((item as { field: string }).field),
    )
    .map((item) => ({
      field: item.field as MessageFilterItem["field"],
      operator: item.operator as MessageFilterItem["operator"],
      value: item.value,
    }));
  if (!items.length) return null;
  const logicOperator = (parsed as { logicOperator?: unknown }).logicOperator === "or" ? "or" : "and";
  return { items, logicOperator };
}

/** Generic listing: ?sourceTopic=&fingerprint=&status=&q=&id=&filter=&sortBy=&sortDir=&page=&pageSize= — the first three take comma lists. */
export const GET = route(async (request: Request) => {
  await requireSession();
  await ensureStamped();
  const url = new URL(request.url);
  const { page, pageSize } = pageParams(url);
  const { items, total } = await listMessages({
    sourceTopic: multi(url, "sourceTopic"),
    fingerprint: multi(url, "fingerprint"),
    status: multi(url, "status"),
    id: url.searchParams.get("id"),
    q: url.searchParams.get("q"),
    filters: filterParam(url),
    sort: sortParam(url),
    page,
    pageSize,
  });
  return NextResponse.json(pageBody(items, total, page, pageSize));
});
