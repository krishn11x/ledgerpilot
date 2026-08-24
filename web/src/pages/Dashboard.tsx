import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { useClearingProof, useMetrics } from "../hooks";

export default function Dashboard() {
  const [latestRunId, setLatestRunId] = useState<string | null>(null);

  useEffect(() => {
    const value = window.localStorage.getItem("ledgerpilot:latest-run");
    setLatestRunId(value);
  }, []);

  const metrics = useMetrics("baseline");
  const proof = useClearingProof();
  const report = metrics.data;

  if (metrics.isLoading) return <p className="text-sm text-ink-muted">Loading evaluation...</p>;
  if (metrics.isError || !report) return <p className="text-sm text-sev-high">Metrics unavailable. Start the API and retry.</p>;

  if (!latestRunId) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <header>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Control room</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">No reconciliation run yet.</h1>
        </header>

        <div className="border border-border-subtle bg-surface p-6">
          <p className="text-sm text-ink-muted">
            Start a reconciliation to see the latest records, exceptions, and value at risk for your uploaded data.
          </p>
          <Link
            to="/workflow"
            className="mt-4 inline-block bg-accent px-4 py-2 text-sm font-medium text-canvas"
          >
            Start Reconciliation
          </Link>
        </div>

        <section className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">System evaluation</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Auto-match rate" value={`${(report.auto_match_rate * 100).toFixed(1)}%`} />
            <MetricCard label="False-positive rate" value={`${(report.false_positive_match_rate * 100).toFixed(2)}%`} />
            <MetricCard label="Unreconciled value" value={formatMinor(report.value_unreconciled_minor, "INR")} />
            <MetricCard label="Records evaluated" value={report.total_records.toLocaleString()} />
          </div>
        </section>
      </div>
    );
  }

  const cards = [
    ["Auto-match rate", `${(report.auto_match_rate * 100).toFixed(1)}%`],
    ["False-positive rate", `${(report.false_positive_match_rate * 100).toFixed(2)}%`],
    ["Unreconciled value", formatMinor(report.value_unreconciled_minor, "INR")],
    ["Records evaluated", report.total_records.toLocaleString()],
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <p className="text-xs uppercase tracking-[0.2em] text-accent">Current reconciliation</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Reconciliation health</h1>
        <p className="mt-2 text-sm text-ink-muted">Latest run: {latestRunId}</p>
      </header>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <MetricCard key={label} label={label} value={value} />
        ))}
      </section>
      <section className="grid gap-4 md:grid-cols-2">
        <div className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">System evaluation</h2>
          <div className="mt-5 space-y-4 text-sm">
            <MetricRow label="Macro precision" value={report.macro_precision} />
            <MetricRow label="Macro recall" value={report.macro_recall} />
          </div>
        </div>
        <div className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">Gateway Clearing proof</h2>
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

function MetricRow({ label, value }: { label: string; value: number }) {
  return <div className="flex justify-between border-b border-border-subtle pb-3"><span className="text-ink-muted">{label}</span><span className="money">{(value * 100).toFixed(1)}%</span></div>;
}

function formatMinor(value: number, currency: string) {
  return `${currency} ${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}
