import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import { queryKeys } from "../lib/queryClient";

export interface BreakSummary {
	break_id: string;
	break_type: string;
	severity: string;
	status: string;
	amount_at_risk_minor: number;
	currency: string;
	summary: string;
}

export interface BreakListResponse {
	items: BreakSummary[];
	total: number;
}

export interface MetricsResponse {
	scenario: string;
	total_records: number;
	auto_match_rate: number;
	false_positive_match_rate: number;
	value_unreconciled_minor: number;
	macro_precision: number;
	macro_recall: number;
}

export function useBreaks() {
	return useQuery({
		queryKey: queryKeys.breaks(),
		queryFn: () => api.get<BreakListResponse>("/breaks?status=open&limit=50"),
	});
}

export function useBreakDetail(breakId: string | undefined) {
	return useQuery({
		queryKey: queryKeys.breakDetail(breakId ?? ""),
		queryFn: () => api.get<{ break: BreakSummary & { legs: { record_id: string; record_type: string; amount_minor: number }[] }; evidence: string }>(`/breaks/${breakId}`),
		enabled: Boolean(breakId),
	});
}

export function useMetrics(scenario = "baseline") {
	return useQuery({
		queryKey: queryKeys.metrics(scenario),
		queryFn: () => api.get<MetricsResponse>(`/metrics?scenario=${scenario}`),
	});
}

export function useClearingProof() {
	return useQuery({
		queryKey: queryKeys.clearingProof,
		queryFn: () => api.get<{ proves_out: boolean; variance_minor: number }>("/ledger/clearing-proof"),
	});
}

export function useAudit() {
	return useQuery({
		queryKey: queryKeys.audit,
		queryFn: () => api.get<{ items: { event_id: string; ts: string; actor: string; action: string; rationale: string }[]; total: number }>("/audit?limit=100"),
	});
}

export function useLedgerEntries() {
	return useQuery({
		queryKey: queryKeys.ledgerEntries,
		queryFn: () => api.get<{ items: { entry_id: string; status: string; rationale: string; lines: { account_code: string; debit_minor: number; credit_minor: number; currency: string }[] }[]; total: number }>("/ledger/entries?limit=100"),
	});
}

export function useDecideBreak() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: ({ breakId, action }: { breakId: string; action: string }) =>
			api.post(`/breaks/${breakId}/decision`, { action }),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.breaks() }),
	});
}
