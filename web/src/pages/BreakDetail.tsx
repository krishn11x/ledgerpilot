import { useParams } from "react-router-dom";

import Placeholder from "../components/ui/Placeholder";

/**
 * Everything a human needs before clicking Approve.
 * SKELETON: phase 7.
 */
export default function BreakDetail() {
  const { breakId } = useParams<{ breakId: string }>();

  return (
    <Placeholder
      title={`Break detail${breakId ? ` -- ${breakId}` : ""}`}
      phase="phase 7"
      summary="The evidence behind a single break: which records are implicated, what the cascade tried, what the agent concluded, and the journal entry being proposed."
      planned={[
        "Evidence chain with every claim linked to a source record",
        "Contradicting evidence shown alongside supporting evidence",
        "Agent reasoning trace, step by step, with the tools it called",
        "Per-feature score breakdown instead of a bare confidence number",
        "Proposed journal entry with its balance check visible",
        "Approve / reject / reassign, recorded against the acting user",
      ]}
    />
  );
}
