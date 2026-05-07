import { useQuery } from "@tanstack/react-query";
import type { Prediction } from "../types";

const STUB_PREDICTIONS: Prediction[] = [
  { id: 1, company: "AAPL", direction: "bullish", confidence: 0.82, reasoning: "Strong RSI reversal combined with positive sentiment surge across multiple news sources. Volume confirms institutional interest.", target_date: "2025-05-14T00:00:00Z", created_at: "2025-05-07T15:00:00Z", signal_count: 3 },
  { id: 2, company: "GOOGL", direction: "bearish", confidence: 0.71, reasoning: "Sustained negative sentiment following regulatory concerns. Technical indicators confirm downward momentum.", target_date: "2025-05-14T00:00:00Z", created_at: "2025-05-07T14:00:00Z", signal_count: 2 },
  { id: 3, company: "MSFT", direction: "bullish", confidence: 0.76, reasoning: "Volume spike aligned with positive earnings revisions. MACD crossover supports near-term upside.", target_date: "2025-05-12T00:00:00Z", created_at: "2025-05-07T13:00:00Z", signal_count: 2 },
  { id: 4, company: "JPM", direction: "bullish", confidence: 0.64, reasoning: "MACD bullish crossover with improving financial sector sentiment.", target_date: "2025-05-10T00:00:00Z", created_at: "2025-05-07T12:00:00Z", signal_count: 1 },
  { id: 5, company: "XOM", direction: "bearish", confidence: 0.68, reasoning: "Technical overbought condition combined with weakening energy sector outlook.", target_date: "2025-05-11T00:00:00Z", created_at: "2025-05-07T11:00:00Z", signal_count: 1 },
];

export function usePredictions(company?: string, direction?: string) {
  return useQuery({
    queryKey: ["predictions", company, direction],
    queryFn: async () => {
      let filtered = STUB_PREDICTIONS;
      if (company) filtered = filtered.filter((p) => p.company === company);
      if (direction) filtered = filtered.filter((p) => p.direction === direction);
      return filtered;
    },
  });
}
