import { useQuery } from "@tanstack/react-query";
import type { NewsArticle, SentimentResult } from "../types";

const STUB_ARTICLES: NewsArticle[] = [
  { id: 1, title: "Apple Reports Record Services Revenue in Q2", summary: "Apple's services segment exceeded expectations, driven by App Store and iCloud growth, pushing total revenue past analyst estimates.", url: "#", source_name: "Reuters", company: "AAPL", published_at: "2025-05-07T16:00:00Z" },
  { id: 2, title: "Microsoft Azure Growth Accelerates to 31%", summary: "Cloud revenue continues to outpace expectations as enterprise AI workload adoption drives Azure consumption higher.", url: "#", source_name: "Bloomberg", company: "MSFT", published_at: "2025-05-07T14:30:00Z" },
  { id: 3, title: "Alphabet Faces New EU Antitrust Probe", summary: "European regulators launch investigation into Google's advertising practices, adding to existing regulatory pressures.", url: "#", source_name: "Financial Times", company: "GOOGL", published_at: "2025-05-07T12:00:00Z" },
  { id: 4, title: "JPMorgan Raises Dividend After Strong Q1", summary: "Bank announces 10% dividend increase following better-than-expected net interest income in the first quarter.", url: "#", source_name: "CNBC", company: "JPM", published_at: "2025-05-07T10:00:00Z" },
  { id: 5, title: "Oil Prices Slip as OPEC+ Signals Production Increase", summary: "Crude benchmarks fall 2% after the cartel hints at easing supply cuts sooner than markets anticipated.", url: "#", source_name: "Reuters", company: "XOM", published_at: "2025-05-07T08:00:00Z" },
  { id: 6, title: "Tech Sector Rally Extends Into Third Week", summary: "Broad-based gains across semiconductor and software names as market sentiment improves on cooling inflation data.", url: "#", source_name: "MarketWatch", company: null, published_at: "2025-05-06T18:00:00Z" },
];

const STUB_SENTIMENT: SentimentResult[] = [
  { symbol: "AAPL", sentiment: 0.72, article_count: 14 },
  { symbol: "MSFT", sentiment: 0.65, article_count: 11 },
  { symbol: "GOOGL", sentiment: -0.35, article_count: 9 },
  { symbol: "JPM", sentiment: 0.48, article_count: 6 },
  { symbol: "XOM", sentiment: -0.22, article_count: 5 },
  { symbol: "JNJ", sentiment: 0.15, article_count: 3 },
];

export function useArticles(company?: string, limit = 50) {
  return useQuery({
    queryKey: ["articles", company, limit],
    queryFn: async () => {
      let filtered = STUB_ARTICLES;
      if (company) filtered = filtered.filter((a) => a.company === company);
      return filtered.slice(0, limit);
    },
  });
}

export function useSearchArticles(query: string) {
  return useQuery({
    queryKey: ["articleSearch", query],
    queryFn: async () => {
      if (!query) return [];
      const q = query.toLowerCase();
      return STUB_ARTICLES.filter(
        (a) => a.title.toLowerCase().includes(q) || a.summary?.toLowerCase().includes(q),
      );
    },
    enabled: !!query,
  });
}

export function useSentiment(symbol?: string) {
  return useQuery({
    queryKey: ["sentiment", symbol],
    queryFn: async () => {
      if (symbol) return STUB_SENTIMENT.filter((s) => s.symbol === symbol);
      return STUB_SENTIMENT;
    },
  });
}
