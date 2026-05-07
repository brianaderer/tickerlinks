import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { NewsArticle, ArticleDetail, SentimentResult } from "../types";

export function useArticles(company?: string, limit = 50) {
  return useQuery({
    queryKey: ["articles", company, limit],
    queryFn: () => {
      const params = new URLSearchParams();
      if (company) params.set("company", company);
      if (limit !== 50) params.set("limit", String(limit));
      const qs = params.toString();
      return apiFetch<NewsArticle[]>(`/articles${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useSearchArticles(query: string) {
  return useQuery({
    queryKey: ["articleSearch", query],
    queryFn: () =>
      apiFetch<NewsArticle[]>(`/articles/search/text?q=${encodeURIComponent(query)}&limit=20`),
    enabled: query.length >= 2,
  });
}

export function useArticle(id: number) {
  return useQuery({
    queryKey: ["article", id],
    queryFn: () => apiFetch<ArticleDetail>(`/articles/${id}`),
    enabled: !!id,
  });
}

export function useArticlesByIds(ids: number[]) {
  return useQuery({
    queryKey: ["articlesBatch", ids],
    queryFn: () => apiFetch<NewsArticle[]>(`/articles/batch?ids=${ids.join(",")}`),
    enabled: ids.length > 0,
  });
}

export function useSentiment(symbol?: string) {
  return useQuery({
    queryKey: ["sentiment", symbol],
    queryFn: () =>
      apiFetch<SentimentResult[]>(
        `/sentiment${symbol ? `?symbol=${symbol}` : ""}`,
      ),
  });
}
