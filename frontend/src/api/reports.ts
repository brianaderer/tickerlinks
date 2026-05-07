import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Report } from "../types";

export function useReports(limit = 10) {
  return useQuery({
    queryKey: ["reports", limit],
    queryFn: () => apiFetch<Report[]>(`/reports?limit=${limit}`),
  });
}

export function useLatestReport() {
  return useQuery({
    queryKey: ["latestReport"],
    queryFn: () => apiFetch<Report>("/reports/latest"),
  });
}

export function useReport(id: number) {
  return useQuery({
    queryKey: ["report", id],
    queryFn: () => apiFetch<Report>(`/reports/${id}`),
    enabled: !!id,
  });
}
