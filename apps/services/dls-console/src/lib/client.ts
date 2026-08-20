"use client";

import type {
  AuditEntry,
  BulkAccepted,
  BulkEdit,
  BulkStatus,
  BulkTarget,
  DiscardResult,
  GroupSummary,
  MessageDetail,
  MessageFilterModel,
  MessageSummary,
  Page,
  ReplayInput,
  ReplayResult,
  SharedFields,
  Stats,
  TopicSummary,
  UndiscardResult,
} from "@/lib/types";

/**
 * Browser-side API client. Same-origin — the app that serves these pages is the
 * app that serves `/api`, so there is no base URL to configure and no CORS.
 */

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    // The routes answer `{detail}`; fall back to the status line for anything
    // that isn't ours (a proxy error page, say).
    const detail = await response
      .json()
      .then((b) => b?.detail)
      .catch(() => null);
    const message =
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : response.statusText;
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | string[] | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(","));
    } else if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  topics: () => request<TopicSummary[]>("/topics"),
  topicGroups: (sourceTopic: string) =>
    request<GroupSummary[]>(`/topics/${encodeURIComponent(sourceTopic)}/groups`),
  allGroups: () => request<GroupSummary[]>("/groups"),

  messages: (params: {
    sourceTopic?: string | string[] | null;
    fingerprint?: string | string[] | null;
    status?: string | string[] | null;
    id?: string | null;
    q?: string | null;
    filter?: MessageFilterModel | null;
    sortBy?: string | null;
    sortDir?: "asc" | "desc" | null;
    page?: number;
    pageSize?: number;
  }) =>
    request<Page<MessageSummary>>(
      `/messages${query({
        ...params,
        filter: params.filter?.items.length ? JSON.stringify(params.filter) : null,
      })}`,
    ),

  message: (id: string) => request<MessageDetail>(`/messages/${id}`),
  messageAudit: (id: string) => request<AuditEntry[]>(`/messages/${id}/audit`),
  neighbours: (id: string, params: { fingerprint?: string | null; status?: string | null }) =>
    request<{ prev: string | null; next: string | null }>(`/messages/${id}/neighbours${query(params)}`),

  replay: (id: string, input: ReplayInput = {}) =>
    request<ReplayResult>(`/messages/${id}/replay`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  discard: (id: string, input: { reason?: string | null } = {}) =>
    request<DiscardResult>(`/messages/${id}/discard`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  undiscard: (id: string) =>
    request<UndiscardResult>(`/messages/${id}/undiscard`, { method: "POST" }),

  bulkReplay: (target: BulkTarget, edit?: BulkEdit | null) =>
    request<BulkAccepted>("/bulk/replay", {
      method: "POST",
      body: JSON.stringify({ target, edit: edit ?? null }),
    }),
  bulkDiscard: (target: BulkTarget, reason?: string | null) =>
    request<BulkAccepted>("/bulk/discard", {
      method: "POST",
      body: JSON.stringify({ target, reason: reason ?? null }),
    }),
  bulkUndiscard: (target: BulkTarget) =>
    request<BulkAccepted>("/bulk/undiscard", { method: "POST", body: JSON.stringify({ target }) }),
  bulkShared: (target: BulkTarget) =>
    request<SharedFields>("/bulk/shared", { method: "POST", body: JSON.stringify({ target }) }),
  bulkStatus: (bulkId: string) => request<BulkStatus>(`/bulk/${bulkId}`),

  stats: () => request<Stats>("/stats"),
};
