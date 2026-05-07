import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_URL } from "./client";
import { useAppStore } from "../store";

const EVENT_TO_QUERIES: Record<string, string[][]> = {
  "signals:analysis_complete": [["predictions"], ["signalMatches"], ["signalDigests"], ["latestReport"]],
  "signals:match_fired":       [["signalMatches"]],
  "signals:ticker_digest":     [["signalDigests"]],
  "prices:update":             [["prices"]],
  "news:article_arrived":      [["articles"]],
  "news:article_processed":    [["articles"], ["articleSearch"], ["sentiment"]],
  "reports:generated":         [["reports"], ["latestReport"]],
  "trends:updated":            [["trends"]],
};

export function useSSE() {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const es = new EventSource(`${API_URL}/stream`);
      esRef.current = es;

      es.onopen = () => useAppStore.getState().setSSEConnected(true);

      es.onerror = () => {
        useAppStore.getState().setSSEConnected(false);
        es.close();
        esRef.current = null;
        if (!unmounted) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };

      for (const eventType of Object.keys(EVENT_TO_QUERIES)) {
        es.addEventListener(eventType, () => {
          for (const key of EVENT_TO_QUERIES[eventType]) {
            queryClient.invalidateQueries({ queryKey: key });
          }
        });
      }

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
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [queryClient]);
}
