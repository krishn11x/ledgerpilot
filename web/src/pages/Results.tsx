import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";

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

  const metricsQuery = useQuery({
    queryKey: ["metrics", "baseline"],
    queryFn: () => api.get<{ auto_match_rate: number; false_positive_match_rate: number; value_unreconciled_minor: number; total_records: number; scenario: string }>("/metrics?scenario=baseline"),
  });

  const summary = useMemo(() => {
    const counts = runQuery.data?.counts ?? {};
    const totalRecords = Number(counts.records ?? counts.total ?? 0);
    const matches = Number(counts.matches ?? 0);
    const breaks = Number(counts.breaks ?? 0);
    const matched = Math.max(0, matches);
    const autoMatch = Number(metricsQuery.data?.auto_match_rate ?? 0);
    const atRisk = Number(metricsQuery.data?.value_unreconciled_minor ?? 0);

    return {
      totalRecords,
      matched,
      exceptions: breaks,
      amountAtRisk: atRisk,
      autoMatchRate: autoMatch,
    };
  }, [metricsQuery.data, runQuery.data]);

  if (runQuery.isLoading || metricsQuery.isLoading) {
    return <p className="text-sm text-ink-muted">Loading reconciliation result…</p>;
  }

  if (runQuery.isError || !runQuery.data) {
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
        <Stat label="Records processed" value={summary.totalRecords.toLocaleString()} />
        <Stat label="Matched" value={summary.matched.toLocaleString()} />
        <Stat label="Exceptions" value={summary.exceptions.toLocaleString()} />
        <Stat label="Amount at risk" value={formatMinor(summary.amountAtRisk, "INR")} />
        <Stat label="Auto-match rate" value={`${(summary.autoMatchRate * 100).toFixed(1)}%`} />
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
