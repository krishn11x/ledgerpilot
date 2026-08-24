import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useClearingProof, useCurrentMetrics } from "../hooks";

export default function Dashboard() {
  const [latestRunId, setLatestRunId] = useState<string | null>(null);

  useEffect(() => {
    const value = window.localStorage.getItem("ledgerpilot:latest-run");
    setLatestRunId(value);
  }, []);

  const proof = useClearingProof();
  const metrics = useCurrentMetrics(latestRunId ?? undefined);

  if (!latestRunId) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <header>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Current reconciliation</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">No reconciliation yet.</h1>
        </header>

        <div className="border border-border-subtle bg-surface p-6">
          <p className="text-sm text-ink-muted">
            Upload a dataset and run reconciliation to see the real result set for this session.
          </p>
          <Link
            to="/workflow"
            className="mt-4 inline-block bg-accent px-4 py-2 text-sm font-medium text-canvas"
          >
            Start Reconciliation
          </Link>
        </div>
      </div>
    );
  }

  if (metrics.isLoading) return <p className="text-sm text-ink-muted">Loading current reconciliation...</p>;
  if (metrics.isError || !metrics.data) return <p className="text-sm text-sev-high">Current reconciliation metrics unavailable.</p>;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <p className="text-xs uppercase tracking-[0.2em] text-accent">Current reconciliation</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Reconciliation health</h1>
        <p className="mt-2 text-sm text-ink-muted">Latest run: {latestRunId}</p>
      </header>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Records checked" value={metrics.data.records_checked.toLocaleString()} />
        <MetricCard label="Matched" value={metrics.data.matched.toLocaleString()} />
        <MetricCard label="Issues found" value={metrics.data.issues_found.toLocaleString()} />
        <MetricCard label="Money needing attention" value={formatMinor(metrics.data.money_needing_attention_minor, "INR")} />
      </section>
      <section className="grid gap-4 md:grid-cols-2">
        <div className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">System evaluation</h2>
          <div className="mt-5 space-y-4 text-sm">
            <MetricRow label="Match rate" value={`${(metrics.data.match_rate * 100).toFixed(1)}%`} />
            <MetricRow label="Run status" value="Completed" />
          </div>
        </div>
        <div className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">Settlement check</h2>
          <p className={`mt-5 text-2xl ${proof.data?.proves_out ? "text-sev-low" : "text-sev-high"}`}>
            {proof.isLoading ? "Checking..." : proof.data?.proves_out ? "In balance" : "Variance detected"}
          </p>
          <p className="money mt-2 text-sm text-ink-muted">Variance: {formatMinor(proof.data?.variance_minor ?? 0, "INR")}</p>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border-subtle bg-surface p-5">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="money mt-3 text-2xl text-ink">{value}</p>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between border-b border-border-subtle pb-3"><span className="text-ink-muted">{label}</span><span className="money">{value}</span></div>;
}

function formatMinor(value: number, currency: string) {
  return `${currency} ${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}
