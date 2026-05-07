import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, API_URL } from "./client";
import type { Prediction } from "../types";

export function usePredictions(company?: string, direction?: string) {
  return useQuery({
    queryKey: ["predictions", company, direction],
    queryFn: () => {
      const params = new URLSearchParams();
      if (company) params.set("company", company);
      if (direction) params.set("direction", direction);
      const qs = params.toString();
      return apiFetch<Prediction[]>(`/predictions${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useRunPrediction(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/predictions/${symbol}/run`, { method: "POST" });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["predictions", symbol] });
        qc.invalidateQueries({ queryKey: ["predictions"] });
      }, 15_000);
    },
  });
}
