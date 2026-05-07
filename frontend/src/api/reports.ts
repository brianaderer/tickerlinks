import { useQuery } from "@tanstack/react-query";
import type { Report } from "../types";

const STUB_REPORTS: Report[] = [
  {
    id: 3, report_type: "hourly", generated_at: "2025-05-07T16:00:00Z",
    summary: "Market showing mixed signals. AAPL bullish on sentiment + technical convergence (82% confidence). GOOGL bearish pressure from regulatory news. Overall signal match rate elevated at 6 new detections this hour.",
    data: {
      total_signals: 6,
      bullish: 4,
      bearish: 2,
      top_prediction: { company: "AAPL", direction: "bullish", confidence: 0.82 },
      active_companies: 5,
    },
  },
  {
    id: 2, report_type: "hourly", generated_at: "2025-05-07T15:00:00Z",
    summary: "Quiet hour with 2 new signal matches. JPM MACD crossover detected. Energy sector showing technical overbought conditions.",
    data: { total_signals: 2, bullish: 1, bearish: 1, active_companies: 2 },
  },
  {
    id: 1, report_type: "hourly", generated_at: "2025-05-07T14:00:00Z",
    summary: "Volume spike detected on MSFT following cloud revenue reports. Sentiment broadly positive across tech sector.",
    data: { total_signals: 3, bullish: 2, bearish: 1, active_companies: 3 },
  },
];

export function useReports(limit = 20) {
  return useQuery({
    queryKey: ["reports", limit],
    queryFn: async () => STUB_REPORTS.slice(0, limit),
  });
}

export function useLatestReport() {
  return useQuery({
    queryKey: ["latestReport"],
    queryFn: async () => STUB_REPORTS[0],
  });
}

export function useReport(id: number) {
  return useQuery({
    queryKey: ["report", id],
    queryFn: async () => STUB_REPORTS.find((r) => r.id === id) ?? null,
    enabled: !!id,
  });
}
