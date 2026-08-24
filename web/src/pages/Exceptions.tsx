import { Link } from "react-router-dom";

import { useBreaks, useDecideBreak } from "../hooks";

/**
 * The exception queue -- a controller's inbox and the primary screen.
 * SKELETON: phase 7.
 */
export default function Exceptions() {
  const breaks = useBreaks();
  const decide = useDecideBreak();
  if (breaks.isLoading) return <p className="text-sm text-ink-muted">Loading exception queue...</p>;
  if (breaks.isError || !breaks.data) return <p className="text-sm text-sev-high">Exception queue unavailable. Start a reconciliation run first.</p>;

  if (breaks.data.total === 0) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <header>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Controller inbox</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">No open exceptions.</h1>
        </header>
        <div className="border border-border-subtle bg-surface p-6 text-sm text-ink-muted">
          <p>Run a reconciliation to review residuals.</p>
          <Link to="/workflow" className="mt-4 inline-block bg-accent px-4 py-2 text-sm font-medium text-canvas">
            Start Reconciliation
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div><p className="text-xs uppercase tracking-[0.2em] text-accent">Controller inbox</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Open exceptions</h1></div>
        <span className="text-sm text-ink-muted">{breaks.data.total} total</span>
      </header>
      <div className="overflow-x-auto border border-border-subtle bg-surface">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="border-b border-border-subtle text-xs uppercase tracking-wider text-ink-faint"><tr><th className="p-4">Break</th><th className="p-4">Severity</th><th className="p-4">Status</th><th className="p-4 text-right">At risk</th><th className="p-4">Action</th></tr></thead>
          <tbody>{breaks.data.items.map((item) => <tr key={item.break_id} className="border-b border-border-subtle last:border-0 hover:bg-surface-raised/50"><td className="p-4"><Link className="font-medium text-accent hover:underline" to={`/exceptions/${item.break_id}`}>{item.break_id}</Link><p className="mt-1 text-xs text-ink-muted">{item.break_type.replaceAll("_", " ")}</p></td><td className="p-4"><span className={`text-sev-${item.severity}`}>{item.severity}</span></td><td className="p-4 text-ink-muted">{item.status}</td><td className="money p-4 text-right">{item.currency} {(item.amount_at_risk_minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td><td className="p-4"><button className="border border-border-subtle px-3 py-1.5 text-xs hover:bg-surface-raised disabled:opacity-50" disabled={decide.isPending} onClick={() => decide.mutate({ breakId: item.break_id, action: "escalate" })}>Escalate</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
