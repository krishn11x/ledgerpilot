import { NavLink } from "react-router-dom";

/**
 * Primary navigation.
 *
 * Ordered by how often a controller uses it, not by information hierarchy:
 * the exception queue is the daily job, the dashboard is a weekly glance.
 */
const NAV = [
  { to: "/exceptions", label: "Exceptions", hint: "Breaks needing a decision" },
  { to: "/dashboard", label: "Dashboard", hint: "Match rate and value at risk" },
  { to: "/ledger", label: "Journal", hint: "Proposed and posted entries" },
  { to: "/audit", label: "Audit log", hint: "Hash-chained event history" },
];

export default function Sidebar() {
  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-border-subtle bg-surface">
      <div className="flex h-14 items-center gap-2 border-b border-border-subtle px-5">
        <span className="size-2 rounded-sm bg-accent" aria-hidden />
        <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
          Ledger&#8202;Pilot
        </span>
      </div>

      <ul className="flex flex-col gap-0.5 p-3">
        {NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              title={item.hint}
              className={({ isActive }) =>
                [
                  "block rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-surface-raised text-ink"
                    : "text-ink-muted hover:bg-surface-raised/60 hover:text-ink",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="mt-auto p-4 text-[10px] leading-relaxed text-ink-faint">
        Deterministic engine clears the bulk of volume. The agent handles only
        the residual, and every proposal is verified by code.
      </div>
    </nav>
  );
}
