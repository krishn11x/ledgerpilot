import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import { useCurrentMetrics } from "../hooks";

export default function Results() {
  const { runId } = useParams<{ runId: string }>();

  useEffect(() => {
    if (runId) {
      window.localStorage.setItem("ledgerpilot:latest-run", runId);
    }
  }, [runId]);

  const runQuery = useQuery({
    queryKey: ["runs", runId],
    queryFn: () => api.get<{ run_id: string; status: string; counts: Record<string, number> }>(`/runs/${runId}`),
    enabled: Boolean(runId),
  });

  const metricsQuery = useCurrentMetrics(runId);

  if (runQuery.isLoading || metricsQuery.isLoading) {
    return <p className="text-sm text-ink-muted">Loading reconciliation result…</p>;
  }

  if (runQuery.isError || metricsQuery.isError || !runQuery.data || !metricsQuery.data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight">Result unavailable</h1>
        <p className="text-sm text-ink-muted">
          The run does not exist yet or it has not completed. Start a new reconciliation to view the outcome.
        </p>
        <Link to="/workflow" className="inline-block border border-border-subtle px-4 py-2 text-sm text-ink">
          Start a new run
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Run summary</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Reconciliation complete</h1>
        </div>
        <span className="rounded-full border border-border-subtle px-3 py-1 text-xs text-ink-muted">
          {runQuery.data.status}
        </span>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Records checked" value={metricsQuery.data.records_checked.toLocaleString()} />
        <Stat label="Matched" value={metricsQuery.data.matched.toLocaleString()} />
        <Stat label="Issues found" value={metricsQuery.data.issues_found.toLocaleString()} />
        <Stat label="Money needing attention" value={formatMinor(metricsQuery.data.money_needing_attention_minor, "INR")} />
        <Stat label="Match rate" value={`${(metricsQuery.data.match_rate * 100).toFixed(1)}%`} />
      </section>

      <section className="border border-border-subtle bg-surface p-5">
        <h2 className="text-sm font-medium">Next step</h2>
        <p className="mt-3 text-sm text-ink-muted">
          Review exceptions to decide whether the remaining residuals should be approved, rejected,
          or escalated.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            to="/exceptions"
            className="bg-accent px-4 py-2 text-sm font-medium text-canvas"
          >
            Review exceptions
          </Link>
          <Link
            to="/dashboard"
            className="border border-border-subtle px-4 py-2 text-sm text-ink hover:bg-surface-raised"
          >
            Open dashboard
          </Link>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border-subtle bg-surface p-4">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="money mt-3 text-xl text-ink">{value}</p>
    </div>
  );
}

function formatMinor(value: number, currency: string) {
  return `${currency} ${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}
