/**
 * Data-fetching hooks.
 *
 * PLACEHOLDER -- one hook per resource, each wrapping `useQuery` with a
 * centralised key from `lib/queryClient`. Keeping keys out of components is
 * what makes cache invalidation after a break decision reliable.
 *
 * Planned:
 *   useBreaks(filters)      exception queue, paged and filtered
 *   useBreakDetail(id)      detail plus evidence chain
 *   useDecideBreak()        mutation; invalidates the queue on success
 *   useRunStream(runId)     SSE subscription for live progress
 *   useMetrics(scenario)    evaluation report
 *   useClearingProof()      the self-proving ledger control
 */

export {};
