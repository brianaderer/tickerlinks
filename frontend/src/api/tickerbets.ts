import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_URL, apiFetch } from "./client";
import type { TickerbetModelRun, TickerbetPrediction } from "../types";

export function useTickerbetRuns(limit = 20) {
  return useQuery({
    queryKey: ["tickerbets", "runs", limit],
    queryFn: () => apiFetch<TickerbetModelRun[]>(`/tickerbets/runs?limit=${limit}`),
    refetchOnWindowFocus: false,
  });
}

export function useLatestTickerbetRun() {
  return useQuery({
    queryKey: ["tickerbets", "latest"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/tickerbets/runs/latest`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<TickerbetModelRun>;
    },
    refetchOnWindowFocus: false,
  });
}

export function useTrainTickerbets() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/tickerbets/train`, { method: "POST" });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<{ status: string; task_id: string }>;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickerbets", "runs"] });
      qc.invalidateQueries({ queryKey: ["tickerbets", "latest"] });
    },
  });
}

export function useGenerateTickerbet() {
  return useMutation({
    mutationFn: async (payload: { symbol: string; target_date: string; run_id?: string }) => {
      const res = await fetch(`${API_URL}/tickerbets/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `API error: ${res.status}`);
      }
      return res.json() as Promise<TickerbetPrediction>;
    },
  });
}
