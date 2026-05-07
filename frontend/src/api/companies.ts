import { useQuery } from "@tanstack/react-query";
import type { Company, PricePoint } from "../types";

const STUB_COMPANIES: Company[] = [
  { id: 1, symbol: "AAPL", name: "Apple Inc.", sector: "Technology", industry: "Consumer Electronics", market_cap: 3200000000000, description: "Consumer electronics and software", indexes: ["SP500", "NDX"] },
  { id: 2, symbol: "MSFT", name: "Microsoft Corp.", sector: "Technology", industry: "Software", market_cap: 3100000000000, description: "Enterprise software and cloud", indexes: ["SP500", "NDX"] },
  { id: 3, symbol: "GOOGL", name: "Alphabet Inc.", sector: "Technology", industry: "Internet Services", market_cap: 2100000000000, description: "Search and advertising", indexes: ["SP500", "NDX"] },
  { id: 4, symbol: "JPM", name: "JPMorgan Chase", sector: "Financial Services", industry: "Banking", market_cap: 680000000000, description: "Global banking and financial services", indexes: ["SP500"] },
  { id: 5, symbol: "JNJ", name: "Johnson & Johnson", sector: "Healthcare", industry: "Pharmaceuticals", market_cap: 420000000000, description: "Healthcare products", indexes: ["SP500"] },
  { id: 6, symbol: "XOM", name: "Exxon Mobil", sector: "Energy", industry: "Oil & Gas", market_cap: 510000000000, description: "Energy and petrochemicals", indexes: ["SP500"] },
];

function generatePrices(base: number, count: number): PricePoint[] {
  const points: PricePoint[] = [];
  let price = base;
  const now = Date.now();
  for (let i = count - 1; i >= 0; i--) {
    const change = (Math.random() - 0.48) * 3;
    price = Math.max(price + change, 10);
    const o = price;
    const h = o + Math.random() * 2;
    const l = o - Math.random() * 2;
    const c = l + Math.random() * (h - l);
    points.push({
      timestamp: new Date(now - i * 3600000).toISOString(),
      open: +o.toFixed(2),
      high: +h.toFixed(2),
      low: +l.toFixed(2),
      close: +c.toFixed(2),
      volume: Math.floor(Math.random() * 50000000) + 1000000,
    });
  }
  return points;
}

export function useCompanies(index?: string) {
  return useQuery({
    queryKey: ["companies", index],
    queryFn: async () => {
      // TODO: replace with apiFetch<Company[]>(`/companies${index ? `?index=${index}` : ""}`)
      return index
        ? STUB_COMPANIES.filter((c) => c.indexes.includes(index))
        : STUB_COMPANIES;
    },
  });
}

export function useCompanyPrices(symbol: string, limit = 100) {
  return useQuery({
    queryKey: ["prices", symbol, limit],
    queryFn: async () => {
      // TODO: replace with apiFetch<PricePoint[]>(`/companies/${symbol}/prices?limit=${limit}`)
      const bases: Record<string, number> = { AAPL: 195, MSFT: 420, GOOGL: 175, JPM: 200, JNJ: 155, XOM: 105 };
      return generatePrices(bases[symbol] || 100, limit);
    },
    enabled: !!symbol,
  });
}
