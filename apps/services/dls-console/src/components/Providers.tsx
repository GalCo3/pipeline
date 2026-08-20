"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

/**
 * React Query is the client-side data layer.
 *
 * The screens are client components against `/api` rather than server
 * components reading Mongo directly, and that is deliberate: a triage console is
 * a live instrument — polling for bulk progress, invalidating after an
 * action, keeping filters in the URL — which is what a query cache is for. It
 * also means the same REST surface the old SPA had stays available to anything
 * else that wants it.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // The dead letter store changes on the pipeline's schedule, not the
            // operator's; a short stale window keeps screens honest without
            // hammering Mongo on every focus event.
            staleTime: 10_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
