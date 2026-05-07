# SSE Frontend Integration Guide

## Connection

Single global stream — all clients receive all events.

```typescript
const API_BASE = "http://localhost:5001/api";
const es = new EventSource(`${API_BASE}/stream`);
```

On reconnect, the browser automatically sends the `Last-Event-ID` header. The server replays any missed events from the Redis buffer (~5000 entries).

## Event Format

Every SSE message uses the pattern `{channel}:{event_type}` as the SSE `event` field:

```
id: 1683456789012-0
event: signals:match_fired
data: {"channel":"signals","event":"match_fired","symbol":"AAPL",...,"ts":"2026-05-07T14:00:00Z"}
```

## Event Catalog

### `signals` channel

| Event | Payload | When |
|-------|---------|------|
| `signals:analysis_started` | `{}` | Signal engine run begins |
| `signals:match_fired` | `{signal, symbol, direction, confidence}` | Individual signal match detected |
| `signals:analysis_complete` | `{predictions, matches}` | Signal engine run finished |

### `prices` channel

| Event | Payload | When |
|-------|---------|------|
| `prices:update` | `{rows}` | Market data fetch completed |

### `news` channel

| Event | Payload | When |
|-------|---------|------|
| `news:article_arrived` | `{count, titles}` | New articles fetched from RSS |
| `news:article_processed` | `{article_id, title, companies}` | Article processed through LLM pipeline |

### `reports` channel

| Event | Payload | When |
|-------|---------|------|
| `reports:generated` | `{report_id, summary}` | Hourly report generated |

### `backtest` channel

| Event | Payload | When |
|-------|---------|------|
| `backtest:window_started` | `{label}` | Backtest window processing begins |
| `backtest:window_complete` | `{label, companies_tested, signal_pairs}` | Backtest window done |

### `signals` channel (continued)

| Event | Payload | When |
|-------|---------|------|
| `signals:ticker_digest` | `{symbol, direction, net_confidence, match_count, digest, matches}` | Per-ticker LLM digest generated after each analysis run |

**Hydration endpoint**: `GET /api/signals/digests` returns the latest set of digests (from the most recent engine run) for page-load.

### `chat` channel

| Event | Payload | When |
|-------|---------|------|
| `chat:thinking` | `{}` | LLM call initiated |
| `chat:token` | `{text}` | Single token from LLM stream |
| `chat:done` | `{text}` | Full response complete |
| `chat:error` | `{error}` | LLM call failed |

### `system` channel

| Event | Payload | When |
|-------|---------|------|
| `system:heartbeat` | `{ts}` | Every 30 seconds (keep-alive) |

## TypeScript Types

```typescript
interface SSEEvent {
  channel: string;
  event: string;
  ts: string;
}

interface SignalMatchEvent extends SSEEvent {
  signal: string;
  symbol: string;
  direction: "bullish" | "bearish" | "neutral";
  confidence: number;
}

interface AnalysisCompleteEvent extends SSEEvent {
  predictions: number;
  matches: number;
}

interface PriceUpdateEvent extends SSEEvent {
  rows: number;
}

interface ArticleArrivedEvent extends SSEEvent {
  count: number;
  titles: string[];
}

interface ArticleProcessedEvent extends SSEEvent {
  article_id: number;
  title: string;
  companies: string[];
}

interface ReportGeneratedEvent extends SSEEvent {
  report_id: number;
  summary: string;
}

interface BacktestWindowEvent extends SSEEvent {
  label: string;
  companies_tested?: number;
  signal_pairs?: number;
}

interface ChatTokenEvent extends SSEEvent {
  text: string;
}

interface ChatDoneEvent extends SSEEvent {
  text: string;
}

interface ChatErrorEvent extends SSEEvent {
  error: string;
}

interface TickerDigestEvent extends SSEEvent {
  symbol: string;
  direction: "bullish" | "bearish" | "neutral";
  net_confidence: number;
  match_count: number;
  digest: string;
  matches: string[];
}
```

## Zustand Integration

```typescript
// store.ts additions
interface SSEState {
  connected: boolean;
  lastEventId: string | null;
  signalMatches: SignalMatchEvent[];
  chatTokens: string;
  chatStreaming: boolean;
}

// Hook to wire SSE into the store
function useSSE() {
  const store = useAppStore();

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/stream`);

    es.addEventListener("signals:match_fired", (e) => {
      const data: SignalMatchEvent = JSON.parse(e.data);
      store.addSignalMatch(data);
    });

    es.addEventListener("chat:token", (e) => {
      const data: ChatTokenEvent = JSON.parse(e.data);
      store.appendChatToken(data.text);
    });

    es.addEventListener("chat:done", (e) => {
      store.finalizeChatMessage();
    });

    es.addEventListener("chat:thinking", () => {
      store.setChatStreaming(true);
    });

    es.addEventListener("reports:generated", (e) => {
      const data: ReportGeneratedEvent = JSON.parse(e.data);
      store.setLatestReport(data);
    });

    es.addEventListener("prices:update", () => {
      store.refreshPrices();
    });

    es.addEventListener("news:article_processed", (e) => {
      const data: ArticleProcessedEvent = JSON.parse(e.data);
      store.addProcessedArticle(data);
    });

    es.onopen = () => store.setConnected(true);
    es.onerror = () => store.setConnected(false);

    return () => es.close();
  }, []);
}
```

## Chat API

Send messages to `POST /api/chat`. The response streams tokens via SSE on the `chat` channel.

```typescript
async function sendChat(messages: ChatMessage[]) {
  // Tokens arrive via SSE — the POST response returns the full text as fallback
  const resp = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
      })),
    }),
  });
  return resp.json(); // { response: "full text" }
}
```

The ChatDrawer should:
1. Call `POST /api/chat` with the conversation history
2. Listen for `chat:token` events on SSE to display tokens as they arrive
3. On `chat:done`, finalize the message in the store
4. The POST response body serves as a fallback if SSE misses events

## Architecture Notes

- The SSE stream is **global broadcast** — all connected clients get all events
- Redis Streams buffer ~5000 events for reconnection replay
- Heartbeat every 30s keeps the connection alive through proxies
- The `id:` field on each event is the Redis Stream ID — used for `Last-Event-ID` reconnection
