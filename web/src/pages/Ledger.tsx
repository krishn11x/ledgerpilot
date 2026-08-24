import { useLedgerEntries } from "../hooks";

export default function Ledger() {
  const ledger = useLedgerEntries();
  if (ledger.isLoading) return <p className="text-sm text-ink-muted">Loading journal...</p>;
  if (ledger.isError || !ledger.data) return <p className="text-sm text-sev-high">Journal unavailable.</p>;
  return <div className="mx-auto max-w-6xl space-y-6"><header><p className="text-xs uppercase tracking-[0.2em] text-accent">Accounting</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Journal entries</h1></header><div className="space-y-3">{ledger.data.items.map((entry) => <div key={entry.entry_id} className="border border-border-subtle bg-surface p-5"><div className="flex justify-between text-sm"><span className="font-medium">{entry.entry_id}</span><span className="text-ink-muted">{entry.status}</span></div><p className="mt-2 text-xs text-ink-muted">{entry.rationale}</p><div className="mt-4 grid gap-2 text-xs sm:grid-cols-2">{entry.lines.map((line, index) => <div key={`${entry.entry_id}-${index}`} className="flex justify-between border-b border-border-subtle py-2"><span>{line.account_code}</span><span className="money">{line.debit_minor ? `Dr ${line.debit_minor}` : `Cr ${line.credit_minor}`} {line.currency}</span></div>)}</div></div>)}</div></div>;
}
