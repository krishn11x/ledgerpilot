/**
 * Shared placeholder for scaffolded screens.
 *
 * States plainly which build phase each screen arrives in. An honest
 * "not built yet" beats a fake chart -- a mock that looks real is the fastest
 * way to lose track of what actually works.
 */
export default function Placeholder({
  title,
  phase,
  summary,
  planned,
}: {
  title: string;
  phase: string;
  summary: string;
  planned: string[];
}) {
  return (
    <section className="mx-auto max-w-3xl">
      <header className="mb-6">
        <div className="mb-2 flex items-center gap-3">
          <h1 className="text-lg font-medium tracking-tight">{title}</h1>
          <span className="rounded-full border border-border-subtle px-2 py-0.5 text-[10px] uppercase tracking-wider text-ink-faint">
            {phase}
          </span>
        </div>
        <p className="text-sm leading-relaxed text-ink-muted">{summary}</p>
      </header>

      <div className="rounded-lg border border-border-subtle bg-surface p-5">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-faint">
          Planned
        </h2>
        <ul className="flex flex-col gap-2">
          {planned.map((item) => (
            <li key={item} className="flex gap-2.5 text-sm text-ink-muted">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-ink-faint" aria-hidden />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
