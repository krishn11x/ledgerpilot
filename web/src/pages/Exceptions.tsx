import Placeholder from "../components/ui/Placeholder";

/**
 * The exception queue -- a controller's inbox and the primary screen.
 * SKELETON: phase 7.
 */
export default function Exceptions() {
  return (
    <Placeholder
      title="Exception queue"
      phase="phase 7"
      summary="Every break the system could not clear on its own, ranked by severity then amount at risk. This is where a human spends their time, so it is the only screen that gets real polish."
      planned={[
        "Filter by break type, status, severity and amount band",
        "Severity-coloured rows with tabular-figure money columns",
        "Inline approve / reject, which resumes the interrupted agent graph",
        "Live arrival of new breaks over SSE while a run is in progress",
        "Bulk-select for breaks sharing a root cause",
      ]}
    />
  );
}
