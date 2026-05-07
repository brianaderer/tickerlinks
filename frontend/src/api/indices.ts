import { useQuery } from "@tanstack/react-query";
import type { Index } from "../types";

const STUB_INDEXES: Index[] = [
  { id: 1, symbol: "SP500", name: "S&P 500", company_count: 4 },
  { id: 2, symbol: "NDX", name: "Nasdaq 100", company_count: 3 },
];

export function useIndexes() {
  return useQuery({
    queryKey: ["indexes"],
    queryFn: async () => STUB_INDEXES,
  });
}
