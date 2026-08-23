import Placeholder from "../components/ui/Placeholder";

/** The hash-chained event log. SKELETON: phase 8. */
export default function AuditLog() {
  return (
    <Placeholder
      title="Audit log"
      phase="phase 8"
      summary="Every decision the system or a human made, append-only and hash-chained so tampering is detectable rather than merely discouraged."
      planned={[
        "Chronological event stream, filterable by subject, actor and action",
        "Actor, rationale and confidence on every entry",
        "Chain-integrity badge from a live recomputation of the hashes",
        "Drill through from any event to the break or match it concerns",
      ]}
    />
  );
}
