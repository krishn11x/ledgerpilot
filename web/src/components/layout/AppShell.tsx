import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Sidebar from "./Sidebar";
import { api } from "../../lib/api";
import { queryKeys } from "../../lib/queryClient";

interface HealthResponse {
  status: string;
  version: string;
  env: string;
  database: string;
  database_reachable: boolean;
  agent_available: boolean;
  autonomy_level: number;
}

const AUTONOMY_LABELS = [
  "L0 detect only",
  "L1 propose only",
  "L2 auto-clear",
  "L3 auto-post",
  "L4 auto-communicate",
];

/**
 * Application chrome.
 *
 * The header shows the backend's live autonomy level and agent availability.
 * That is not decoration: "what policy is this instance running under" is the
 * first question anyone asks about a reconciliation result, and it should be
 * visible at all times rather than buried in a settings page.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const { data: health, isError } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.get<HealthResponse>("/health"),
    refetchInterval: 60_000,
  });

  const connected = !isError && health?.database_reachable;

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border-subtle px-6">
          <div className="flex items-baseline gap-3">
            <span className="text-sm font-medium tracking-tight">LedgerPilot</span>
            <span className="text-xs text-ink-faint">AI Finance Controller</span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <Link
              to="/workflow"
              className="rounded-full bg-accent px-3 py-1.5 font-medium text-canvas"
            >
              Get Started
            </Link>
            <Pill
              label="Auto-resolution enabled"
              title={health ? AUTONOMY_LABELS[health.autonomy_level] ?? "unknown" : "autonomy ..."}
            />
            <Pill
              label={
                health?.agent_available
                  ? "Agent ready"
                  : "External LLM not configured — deterministic agent mode available."
              }
              tone={health?.agent_available ? "good" : "muted"}
              title={health?.agent_available ? "LLM integration is configured" : "No external LLM key configured; deterministic mode remains active."}
            />
            <span className="flex items-center gap-1.5 text-ink-faint">
              <span
                className={`size-1.5 rounded-full ${
                  connected ? "bg-sev-low" : "bg-sev-high"
                }`}
                aria-hidden
              />
              {connected ? health?.database : "api unreachable"}
            </span>
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}

function Pill({ label, tone = "muted", title }: { label: string; tone?: "good" | "muted"; title?: string }) {
  return (
    <span
      title={title}
      className={`rounded-full border border-border-subtle px-2.5 py-1 ${
        tone === "good" ? "text-sev-low" : "text-ink-muted"
      }`}
    >
      {label}
    </span>
  );
}
