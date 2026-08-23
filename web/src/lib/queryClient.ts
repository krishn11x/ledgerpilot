import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api";

/**
 * All server state lives here -- caching, polling and invalidation come free,
 * so no Redux and no hand-rolled fetch hooks.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // A scaffolded endpoint (501) or a client error will not fix itself.
        if (error instanceof ApiError && error.status < 500) return false;
        return failureCount < 2;
      },
    },
  },
});

/** Centralised query keys so invalidation after a decision cannot miss a cache. */
export const queryKeys = {
  health: ["health"] as const,
  scenarios: ["scenarios"] as const,
  breaks: (filters?: Record<string, unknown>) => ["breaks", filters ?? {}] as const,
  breakDetail: (id: string) => ["breaks", id] as const,
  match: (id: string) => ["matches", id] as const,
  ledgerEntries: ["ledger", "entries"] as const,
  clearingProof: ["ledger", "clearing-proof"] as const,
  audit: ["audit"] as const,
  metrics: (scenario: string) => ["metrics", scenario] as const,
};
