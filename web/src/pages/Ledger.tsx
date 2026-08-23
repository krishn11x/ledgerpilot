import Placeholder from "../components/ui/Placeholder";

/** Proposed and posted journal entries. SKELETON: phase 7. */
export default function Ledger() {
  return (
    <Placeholder
      title="Journal entries"
      phase="phase 7"
      summary="Double-entry postings proposed for resolved breaks. Nothing posts without either a human approval or an explicit autonomy-level-3 policy allowing it."
      planned={[
        "Entry list filtered by status: proposed, approved, posted, voided",
        "Debit and credit lines with the balance assertion shown",
        "Rationale and the break each entry derives from",
        "Approve-and-post, re-checking balance at commit time",
        "Gateway Clearing account roll-forward",
      ]}
    />
  );
}
