import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_URL } from "./client";
import { useAppStore } from "../store";
import type { NewsArticle } from "../types";

export function useSSE() {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (esRef.current && esRef.current.readyState !== EventSource.CLOSED) return;

    const es = new EventSource(`${API_URL}/stream`);
    esRef.current = es;

    es.onopen = () => {
      retryCount.current = 0;
      useAppStore.getState().setSSEConnected(true);
    };

    es.onerror = () => {
      useAppStore.getState().setSSEConnected(false);
      es.close();
      esRef.current = null;
      retryCount.current += 1;
      const delay = Math.min(5000 * Math.pow(2, retryCount.current - 1), 60000);
      reconnectTimer.current = setTimeout(connect, delay);
    };

    // -- Data-carrying events: update cache directly, no refetch --

    es.addEventListener("news:article_processed", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const article: NewsArticle = {
          id: data.article_id,
          title: data.title,
          summary: data.summary || null,
          url: data.url || "",
          source_name: data.source_name || "",
          companies: (data.companies || []).map((s: string) => ({ symbol: s, sentiment: "neutral", relevance: "primary" })),
          published_at: data.published_at || null,
          fetched_at: data.fetched_at || null,
        };
        queryClient.setQueryData<NewsArticle[]>(["articles", undefined, 50], (old) =>
          old ? [article, ...old.filter((a) => a.id !== article.id)] : [article]
        );
      } catch { /* ignore malformed */ }
    });

    es.addEventListener("news:article_arrived", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.articles && Array.isArray(data.articles)) {
          queryClient.setQueryData<NewsArticle[]>(["articles", undefined, 50], (old) => {
            if (!old) return old;
            const newArticles = data.articles as NewsArticle[];
            const ids = new Set(old.map((a) => a.id));
            return [...newArticles.filter((a: NewsArticle) => !ids.has(a.id)), ...old];
          });
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signals:analysis_complete", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.predictions) {
          queryClient.setQueryData(["predictions"], data.predictions);
        }
        if (data.matches) {
          queryClient.setQueryData(["signalMatches"], data.matches);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signals:ticker_digest", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        queryClient.setQueryData<unknown[]>(["signalDigests"], (old) =>
          old ? [...old.filter((d: any) => d.symbol !== data.symbol), data] : [data]
        );
      } catch { /* ignore */ }
    });

    es.addEventListener("reports:generated", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.report) {
          queryClient.setQueryData(["latestReport"], data.report);
          queryClient.setQueryData<unknown[]>(["reports"], (old) =>
            old ? [data.report, ...old] : [data.report]
          );
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("prices:update", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.prices) {
          queryClient.setQueryData(["prices", data.symbol], (old: unknown[] | undefined) =>
            data.prices || old
          );
        }
      } catch { /* ignore */ }
    });

    // -- Chat streaming --

    es.addEventListener("chat:thinking", () => {
      useAppStore.getState().setChatStreaming(true);
    });

    es.addEventListener("chat:token", (e: MessageEvent) => {
      try {
        useAppStore.getState().appendChatToken(JSON.parse(e.data).text);
      } catch { /* ignore */ }
    });

    es.addEventListener("chat:done", (e: MessageEvent) => {
      try {
        useAppStore.getState().finalizeChatMessage(JSON.parse(e.data).text);
      } catch { /* ignore */ }
    });

    es.addEventListener("chat:error", (e: MessageEvent) => {
      try {
        useAppStore.getState().finalizeChatMessage(`Error: ${JSON.parse(e.data).error}`);
      } catch { /* ignore */ }
    });
  }, [queryClient]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);
}
