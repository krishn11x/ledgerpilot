import { useClearingProof, useMetrics } from "../hooks";

export default function Dashboard() {
  const metrics = useMetrics();
  const proof = useClearingProof();
  const report = metrics.data;

  if (metrics.isLoading) return <p className="text-sm text-ink-muted">Loading evaluation...</p>;
  if (metrics.isError || !report) return <p className="text-sm text-sev-high">Metrics unavailable. Start the API and retry.</p>;

  const cards = [
    ["Auto-match rate", `${(report.auto_match_rate * 100).toFixed(1)}%`],
    ["False-positive rate", `${(report.false_positive_match_rate * 100).toFixed(2)}%`],
    ["Unreconciled value", formatMinor(report.value_unreconciled_minor, "INR")],
    ["Records evaluated", report.total_records.toLocaleString()],
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <p className="text-xs uppercase tracking-[0.2em] text-accent">Control room</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Reconciliation health</h1>
        <p className="mt-2 text-sm text-ink-muted">Deterministic engine benchmark, scenario: {report.scenario}.</p>
      </header>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="border border-border-subtle bg-surface p-5">
            <p className="text-xs text-ink-faint">{label}</p>
            <p className="money mt-3 text-2xl text-ink">{value}</p>
          </div>
        ))}
      </section>
      <section className="grid gap-4 md:grid-cols-2">
        <div className="border border-border-subtle bg-surface p-5">
          <h2 className="text-sm font-medium">Evaluation quality</h2>
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

function MetricRow({ label, value }: { label: string; value: number }) {
  return <div className="flex justify-between border-b border-border-subtle pb-3"><span className="text-ink-muted">{label}</span><span className="money">{(value * 100).toFixed(1)}%</span></div>;
}

function formatMinor(value: number, currency: string) {
  return `${currency} ${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}
