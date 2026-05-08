import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_URL } from "./client";
import { useAppStore } from "../store";

export function useSSE() {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const retryCount = useRef(0);
  const ready = useRef(false);

  const getLastId = () => sessionStorage.getItem("sse:lastEventId") || "$";
  const setLastId = (id: string) => sessionStorage.setItem("sse:lastEventId", id);

  const connect = useCallback(() => {
    if (esRef.current && esRef.current.readyState !== EventSource.CLOSED) return;

    const es = new EventSource(`${API_URL}/stream?last_id=${encodeURIComponent(getLastId())}`);
    esRef.current = es;
    ready.current = false;

    es.onopen = () => {
      retryCount.current = 0;
      useAppStore.getState().setSSEConnected(true);
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

    const trackId = (e: MessageEvent) => { if (e.lastEventId) setLastId(e.lastEventId); };

    // -- Data-carrying events: update cache directly, no refetch --

    // news:article_processed is ignored -- the backend fires this for every article
    // in the processing backlog (thousands), which would flood the UI.
    // Headlines are hydrated once via fetch; only brand-new RSS arrivals update them.

    es.addEventListener("news:article_arrived", (e: MessageEvent) => {
      trackId(e);
      if (!ready.current) return;
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    });

    es.addEventListener("signals:analysis_started", (e: MessageEvent) => {
      trackId(e);
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        if (data.mode === "manual" && data.symbol) {
          useAppStore.getState().addPendingPrediction(data.symbol);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signals:analysis_complete", (e: MessageEvent) => {
      trackId(e);
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        if (data.mode === "manual" && data.symbol) {
          useAppStore.getState().removePendingPrediction(data.symbol);
          if (data.prediction) {
            queryClient.setQueryData(["predictions", data.symbol, undefined], (old: unknown[] | undefined) => {
              const existing = (old || []) as any[];
              return [data.prediction, ...existing.filter((p: any) => p.id !== data.prediction.id)];
            });
            queryClient.setQueryData(["predictions", undefined, undefined], (old: unknown[] | undefined) => {
              if (!old) return old;
              const existing = old as any[];
              return [data.prediction, ...existing.filter((p: any) => p.company !== data.symbol)];
            });
          }
        }
      } catch { /* ignore */ }
    });

    es.addEventListener("signals:ticker_digest", (e: MessageEvent) => {
      trackId(e);
      if (!ready.current) return;
      try {
        const data = JSON.parse(e.data);
        queryClient.setQueryData<unknown[]>(["signalDigests"], (old) =>
          old ? [...old.filter((d: any) => d.symbol !== data.symbol), data] : [data]
        );
      } catch { /* ignore */ }
    });

    es.addEventListener("reports:generated", () => {
      if (!ready.current) return;
      queryClient.invalidateQueries({ queryKey: ["latestReport"] });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    });

    es.addEventListener("prices:update", (e: MessageEvent) => {
      trackId(e);
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
      trackId(e);
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
