import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { TrendSnapshot } from "../types";

export function useTrends() {
  return useQuery({
    queryKey: ["trends"],
    queryFn: () => apiFetch<TrendSnapshot>("/trends"),
  });
}
