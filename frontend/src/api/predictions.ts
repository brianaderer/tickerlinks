import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
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
