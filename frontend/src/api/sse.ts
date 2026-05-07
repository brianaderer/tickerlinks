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
  const ready = useRef(false);

  const connect = useCallback(() => {
    if (esRef.current && esRef.current.readyState !== EventSource.CLOSED) return;

    // Connect with $, which means "only new events from now on" -- skip the Redis replay buffer
    const es = new EventSource(`${API_URL}/stream?last_id=$`);
    esRef.current = es;
    ready.current = false;

    es.onopen = () => {
      retryCount.current = 0;
      useAppStore.getState().setSSEConnected(true);
      // Small delay to skip any burst of buffered events that arrive right after open
      setTimeout(() => { ready.current = true; }, 500);
    };

    es.onerror = () => {
      useAppStore.getState().setSSEConnected(false);
      ready.current = false;
      es.close();
      esRef.current = null;
      retryCount.current += 1;
      const delay = Math.min(5000 * Math.pow(2, retryCount.current - 1), 60000);
      reconnectTimer.current = setTimeout(connect, delay);
    };

    // -- Data-carrying events: update cache directly, no refetch --

    // news:article_processed is ignored -- the backend fires this for every article
    // in the processing backlog (thousands), which would flood the UI.
    // Headlines are hydrated once via fetch; only brand-new RSS arrivals update them.

    es.addEventListener("news:article_arrived", (e: MessageEvent) => {
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        if (data.articles && Array.isArray(data.articles)) {
          queryClient.setQueryData<NewsArticle[]>(["articles", undefined, 50], (old) => {
            if (!old) return old;
            const newArticles = data.articles as NewsArticle[];
            const ids = new Set(old.map((a) => a.id));
            const merged = [...newArticles.filter((a: NewsArticle) => !ids.has(a.id)), ...old];
            return merged.slice(0, 50);
          });
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signals:analysis_complete", (e: MessageEvent) => {
      if (!ready.current) return;
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
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        queryClient.setQueryData<unknown[]>(["signalDigests"], (old) =>
          old ? [...old.filter((d: any) => d.symbol !== data.symbol), data] : [data]
        );
      } catch { /* ignore */ }
    });

    es.addEventListener("reports:generated", (e: MessageEvent) => {
      if (!ready.current) return;
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
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.prices) {
          queryClient.setQueryData(["prices", data.symbol], (old: unknown[] | undefined) =>
            data.prices || old
          );
        }
      } catch { /* ignore */ }
    });

    // Chat events are handled by the fetch response in ChatDrawer.
    // SSE chat events are only used for tool-call status indicators.

    es.addEventListener("trends:updated", () => {
      if (!ready.current) return;
      queryClient.invalidateQueries({ queryKey: ["trends"] });
      queryClient.invalidateQueries({ queryKey: ["articlesBatch"] });
    });

    es.addEventListener("chat:tool_call", (e: MessageEvent) => {
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        useAppStore.getState().setChatToolStatus(data.tool);
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
