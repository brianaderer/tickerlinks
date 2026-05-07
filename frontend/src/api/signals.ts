import { useQuery } from "@tanstack/react-query";
import type { Signal, SignalMatch, SignalWeight } from "../types";

const STUB_SIGNALS: Signal[] = [
  { id: 1, name: "RSI Oversold", signal_type: "technical", direction: "bullish", description: "RSI drops below 30", parameters: { period: 14, threshold: 30 }, historical_accuracy: 0.72, sample_size: 340, weight: 0.72, match_count: 18 },
  { id: 2, name: "RSI Overbought", signal_type: "technical", direction: "bearish", description: "RSI exceeds 70", parameters: { period: 14, threshold: 70 }, historical_accuracy: 0.68, sample_size: 290, weight: 0.68, match_count: 12 },
  { id: 3, name: "Volume Spike", signal_type: "volume", direction: "bullish", description: "Volume exceeds 2x 20-day average", parameters: { multiplier: 2, window: 20 }, historical_accuracy: 0.61, sample_size: 150, weight: 0.61, match_count: 22 },
  { id: 4, name: "Sentiment Surge", signal_type: "sentiment", direction: "bullish", description: "Aggregate sentiment score exceeds 0.7", parameters: { threshold: 0.7 }, historical_accuracy: 0.65, sample_size: 80, weight: 0.65, match_count: 9 },
  { id: 5, name: "Negative Sentiment", signal_type: "sentiment", direction: "bearish", description: "Aggregate sentiment drops below -0.5", parameters: { threshold: -0.5 }, historical_accuracy: 0.70, sample_size: 95, weight: 0.70, match_count: 7 },
  { id: 6, name: "MACD Crossover", signal_type: "technical", direction: "bullish", description: "MACD line crosses above signal line", parameters: { fast: 12, slow: 26, signal: 9 }, historical_accuracy: 0.63, sample_size: 200, weight: 0.63, match_count: 14 },
  { id: 7, name: "Mention Velocity", signal_type: "mention", direction: "bullish", description: "News mention rate accelerates 3x", parameters: { multiplier: 3 }, historical_accuracy: 0.58, sample_size: 60, weight: 0.58, match_count: 5 },
  { id: 8, name: "Source Breadth", signal_type: "mention", direction: "bullish", description: "Coverage from 5+ unique sources in 24h", parameters: { min_sources: 5, window_hours: 24 }, historical_accuracy: 0.66, sample_size: 45, weight: 0.66, match_count: 4 },
];

const STUB_MATCHES: SignalMatch[] = [
  { id: 1, signal: "RSI Oversold", signal_type: "technical", company: "AAPL", direction: "bullish", confidence: 0.85, context: { rsi: 28.3 }, detected_at: "2025-05-07T14:30:00Z" },
  { id: 2, signal: "Volume Spike", signal_type: "volume", company: "MSFT", direction: "bullish", confidence: 0.72, context: { volume_ratio: 2.4 }, detected_at: "2025-05-07T13:00:00Z" },
  { id: 3, signal: "Negative Sentiment", signal_type: "sentiment", company: "GOOGL", direction: "bearish", confidence: 0.78, context: { score: -0.62 }, detected_at: "2025-05-07T12:00:00Z" },
  { id: 4, signal: "MACD Crossover", signal_type: "technical", company: "JPM", direction: "bullish", confidence: 0.65, context: { macd: 1.2, signal_line: 0.8 }, detected_at: "2025-05-07T11:00:00Z" },
  { id: 5, signal: "Sentiment Surge", signal_type: "sentiment", company: "AAPL", direction: "bullish", confidence: 0.91, context: { score: 0.82 }, detected_at: "2025-05-07T10:00:00Z" },
  { id: 6, signal: "RSI Overbought", signal_type: "technical", company: "XOM", direction: "bearish", confidence: 0.74, context: { rsi: 73.1 }, detected_at: "2025-05-07T09:30:00Z" },
];

const STUB_WEIGHTS: SignalWeight[] = STUB_SIGNALS.map((s) => ({
  signal: s.name,
  direction: s.direction,
  signal_type: s.signal_type,
  weight: s.weight,
  sample_size: s.sample_size,
  snapshots: Math.floor(s.sample_size / 10),
}));

export function useSignals() {
  return useQuery({
    queryKey: ["signals"],
    queryFn: async () => STUB_SIGNALS,
  });
}

export function useSignalMatches(company?: string, type?: string) {
  return useQuery({
    queryKey: ["signalMatches", company, type],
    queryFn: async () => {
      let filtered = STUB_MATCHES;
      if (company) filtered = filtered.filter((m) => m.company === company);
      if (type) filtered = filtered.filter((m) => m.signal_type === type);
      return filtered;
    },
  });
}

export function useSignalWeights() {
  return useQuery({
    queryKey: ["signalWeights"],
    queryFn: async () => STUB_WEIGHTS,
  });
}
