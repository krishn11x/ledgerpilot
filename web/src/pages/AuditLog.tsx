import { useAudit } from "../hooks";

export default function AuditLog() {
  const audit = useAudit();
  if (audit.isLoading) return <p className="text-sm text-ink-muted">Loading audit log...</p>;
  if (audit.isError || !audit.data) return <p className="text-sm text-sev-high">Audit log unavailable.</p>;

  if (audit.data.items.length === 0) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <header>
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Evidence</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Audit log</h1>
        </header>
        <div className="border border-border-subtle bg-surface p-6 text-sm text-ink-muted">
          No audit events yet. Decisions and system actions will appear here.
        </div>
      </div>
    );
  }

  return <div className="mx-auto max-w-6xl space-y-6"><header><p className="text-xs uppercase tracking-[0.2em] text-accent">Evidence</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Audit log</h1></header><div className="border border-border-subtle bg-surface">{audit.data.items.map((event) => <div key={event.event_id} className="border-b border-border-subtle p-4 last:border-0"><div className="flex flex-wrap justify-between gap-2 text-sm"><span className="font-medium">{event.action}</span><span className="text-ink-faint">{new Date(event.ts).toLocaleString()}</span></div><p className="mt-1 text-xs text-ink-muted">{event.actor} · {event.rationale}</p></div>)}</div></div>;
}
