import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Company, PricePoint } from "../types";

export function useCompanies(index?: string) {
  return useQuery({
    queryKey: ["companies", index],
    queryFn: () =>
      apiFetch<Company[]>(`/companies${index ? `?index=${index}` : ""}`),
  });
}

export function useCompanyPrices(symbol: string, limit = 100) {
  return useQuery({
    queryKey: ["prices", symbol, limit],
    queryFn: async () => {
      const data = await apiFetch<PricePoint[]>(
        `/companies/${symbol}/prices?limit=${limit}`,
      );
      return data.reverse();
    },
    enabled: !!symbol,
  });
}
