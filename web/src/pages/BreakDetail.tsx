import { useParams } from "react-router-dom";

import { useBreakDetail, useDecideBreak } from "../hooks";

export default function BreakDetail() {
  const { breakId } = useParams<{ breakId: string }>();
  const detail = useBreakDetail(breakId);
  const decide = useDecideBreak();

  if (detail.isLoading) return <p className="text-sm text-ink-muted">Loading break...</p>;
  if (detail.isError || !detail.data) return <p className="text-sm text-sev-high">Break unavailable.</p>;
  const item = detail.data.break;
  const action = (name: string) => decide.mutate({ breakId: item.break_id, action: name });
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-[0.2em] text-accent">Exception evidence</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">{item.break_id}</h1><p className="mt-2 text-sm text-ink-muted">{item.summary}</p></div><span className={`text-sm text-sev-${item.severity}`}>{item.severity}</span></header>
      <section className="grid gap-4 md:grid-cols-3"><Stat label="Type" value={item.break_type.replaceAll("_", " ")} /><Stat label="Status" value={item.status} /><Stat label="At risk" value={`${item.currency} ${(item.amount_at_risk_minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} /></section>
      <section className="border border-border-subtle bg-surface p-5"><h2 className="text-sm font-medium">Impacted records</h2><div className="mt-4 grid gap-2 sm:grid-cols-2">{item.legs.map((leg) => <div key={leg.record_id} className="flex justify-between border-b border-border-subtle py-2 text-sm"><span><span className="text-ink-muted">{leg.record_type}</span> {leg.record_id}</span><span className="money">{(leg.amount_minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>)}</div></section>
      <section className="border border-border-subtle bg-surface p-5"><h2 className="text-sm font-medium">Evidence trace</h2><pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-ink-muted">{detail.data.evidence || "No audit evidence recorded yet."}</pre></section>
      <div className="flex flex-wrap gap-2"><button className="bg-accent px-4 py-2 text-sm text-canvas disabled:opacity-50" disabled={decide.isPending} onClick={() => action("approve")}>Approve</button><button className="border border-border-subtle px-4 py-2 text-sm hover:bg-surface-raised disabled:opacity-50" disabled={decide.isPending} onClick={() => action("reject")}>Reject</button><button className="border border-border-subtle px-4 py-2 text-sm hover:bg-surface-raised disabled:opacity-50" disabled={decide.isPending} onClick={() => action("escalate")}>Escalate</button></div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="border border-border-subtle bg-surface p-4"><p className="text-xs text-ink-faint">{label}</p><p className="mt-2 text-sm capitalize">{value}</p></div>;
}
