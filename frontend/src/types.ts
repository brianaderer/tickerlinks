export interface Index {
  id: number;
  symbol: string;
  name: string;
  company_count: number;
}

export interface Company {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  market_cap: number;
  description: string;
  indexes: string[];
}

export interface PricePoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FeedSource {
  id: number;
  name: string;
  url: string;
  source_type: string;
  active: boolean;
  last_polled: string | null;
}

export interface ArticleCompany {
  symbol: string;
  sentiment: string;
  relevance: string;
}

export interface NewsArticle {
  id: number;
  title: string;
  summary: string | null;
  url: string;
  source_name: string;
  content_source: "scraped" | "summary" | null;
  companies: ArticleCompany[];
  published_at: string | null;
  fetched_at: string | null;
}

export interface ArticleDetail extends NewsArticle {
  full_text: string | null;
  author: string | null;
  fetched_at: string | null;
}

export interface Signal {
  id: number;
  name: string;
  signal_type: string;
  direction: string;
  description: string;
  parameters: Record<string, unknown>;
  historical_accuracy: number;
  sample_size: number;
  weight: number;
  match_count: number;
}

export interface SignalMatch {
  id: number;
  signal: string;
  signal_type: string;
  company: string;
  direction: string;
  confidence: number;
  context: Record<string, unknown>;
  detected_at: string;
  source_at: string | null;
}

export interface SignalWeight {
  signal: string;
  direction: string;
  signal_type: string;
  weight: number;
  sample_size: number;
  snapshots: number;
}

export interface Trend {
  rank: number;
  headline: string;
  impact: string;
  top_tags: string[];
  article_ids: number[];
  companies: string[];
  first_seen: string;
  latest: string;
}

export interface TrendSnapshot {
  generated_at: string | null;
  trends: Trend[];
}

export interface SignalDigest {
  symbol: string;
  direction: string;
  net_confidence: number;
  match_count: number;
  digest: string;
  matches: string[];
  generated_at: string;
}

export interface Prediction {
  id: number;
  company: string;
  direction: string;
  confidence: number;
  magnitude: number | null;
  reasoning: string;
  target_date: string | null;
  created_at: string;
  signal_count: number;
}

export interface SentimentResult {
  symbol: string;
  sentiment_score: number;
  total_mentions: number;
  bullish: number;
  bearish: number;
  neutral: number;
  primary_mentions: number;
}

export interface Report {
  id: number;
  report_type: string;
  generated_at: string;
  summary: string;
  data?: Record<string, unknown>;
}

export interface TickerbetModelRun {
  id: number;
  run_id: string;
  status: "running" | "succeeded" | "failed";
  model_family: string;
  started_at: string | null;
  completed_at: string | null;
  training_window_start: string | null;
  training_window_end: string | null;
  company_count: number;
  sample_count: number;
  train_count: number;
  test_count: number;
  feature_columns: Record<string, string[]>;
  metrics: Record<string, Record<string, number>>;
  artifact_prefix: string | null;
  dataset_key: string | null;
  model_keys: Record<string, string>;
  metadata_key: string | null;
  error: string | null;
}

export interface TickerbetPrediction {
  symbol: string;
  requested_target_date: string;
  resolved_target_date: string;
  horizon_days: number;
  as_of: string;
  current_price: number;
  predicted_price: number;
  predicted_delta: number;
  predicted_delta_pct: number;
  run_id: string;
  metrics: Record<string, number>;
}
