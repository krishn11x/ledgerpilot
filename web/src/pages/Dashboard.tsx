import Placeholder from "../components/ui/Placeholder";

/** Run KPIs and evaluation metrics. SKELETON: phase 8. */
export default function Dashboard() {
  return (
    <Placeholder
      title="Dashboard"
      phase="phase 8"
      summary="Reconciliation health at a glance, plus the evaluation metrics measured against synthetic ground truth."
      planned={[
        "Auto-match rate, split between the engine alone and engine plus agent",
        "Value unreconciled and value at risk, in base currency",
        "Break mix by type and severity",
        "Precision / recall per break type, and the false-positive match rate",
        "Gateway Clearing proof: balance versus captured-but-unsettled",
        "Autonomy dial, to show the queue drain as the level is raised",
      ]}
    />
  );
}
