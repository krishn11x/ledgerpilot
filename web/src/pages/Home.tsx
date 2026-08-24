import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section className="rounded-lg border border-border-subtle bg-surface p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-accent">LedgerPilot</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight">Reconcile payments without the spreadsheet headache.</h1>
        <p className="mt-4 max-w-2xl text-base text-ink-muted">
          Upload your orders, gateway transactions, payouts and bank statement. LedgerPilot checks them,
          finds issues, explains them and helps you resolve them.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/workflow" className="bg-accent px-5 py-3 text-sm font-medium text-canvas">
            Start a reconciliation
          </Link>
          <Link to="/workflow" className="border border-border-subtle px-5 py-3 text-sm text-ink hover:bg-surface-raised">
            Try a demo
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Panel title="Upload your data" text="Bring in the four source files that drive the reconciliation." />
        <Panel title="Review issues" text="See only the problems from the current run and explain the root cause." />
        <Panel title="Resolve quickly" text="Approve, reject or escalate decisions with an audit trail attached." />
      </section>

      <div className="border border-border-subtle bg-surface p-6 text-sm text-ink-muted">
        <p className="font-medium text-ink">No reconciliation yet.</p>
        <p className="mt-2">Your latest reconciliation will appear here after you upload and run a dataset.</p>
      </div>
    </div>
  );
}

function Panel({ title, text }: { title: string; text: string }) {
  return (
    <div className="border border-border-subtle bg-surface p-5">
      <h2 className="text-lg font-medium text-ink">{title}</h2>
      <p className="mt-2 text-sm text-ink-muted">{text}</p>
    </div>
  );
}
