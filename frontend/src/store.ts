import { create } from "zustand";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface AppState {
  selectedSymbol: string | null;
  sidebarOpen: boolean;
  activeSignalType: string | null;
  chatOpen: boolean;
  chatMessages: ChatMessage[];
  chatStreaming: boolean;
  chatToolStatus: string | null;
  pageContext: string;
  sseConnected: boolean;
  pendingPredictions: Set<string>;
  pendingPredictionStartedAt: Record<string, number>;

  setSelectedSymbol: (symbol: string | null) => void;
  toggleSidebar: () => void;
  setActiveSignalType: (type: string | null) => void;
  toggleChat: () => void;
  setChatOpen: (open: boolean) => void;
  addChatMessage: (msg: ChatMessage) => void;
  setPageContext: (ctx: string) => void;
  setSSEConnected: (connected: boolean) => void;
  setChatStreaming: (streaming: boolean) => void;
  setChatToolStatus: (tool: string | null) => void;
  addPendingPrediction: (symbol: string, startedAt?: number) => void;
  removePendingPrediction: (symbol: string) => void;
  pruneStalePendingPredictions: () => void;
}

const PENDING_PREDICTIONS_KEY = "pendingPredictions";
const PENDING_TTL_MS = 5 * 60 * 1000;

function sanitizePendingPredictionMap(map: Record<string, number>) {
  const now = Date.now();
  return Object.fromEntries(
    Object.entries(map).filter(([, ts]) => Number.isFinite(ts) && now - ts <= PENDING_TTL_MS),
  ) as Record<string, number>;
}

function loadPendingPredictionMap(): Record<string, number> {
  if (typeof sessionStorage === "undefined") return {};
  const raw = sessionStorage.getItem(PENDING_PREDICTIONS_KEY);
  if (!raw) return {};

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return {};
    }
    const map: Record<string, number> = {};
    for (const [symbol, value] of Object.entries(parsed as Record<string, unknown>)) {
      const ts = Number(value);
      if (Number.isFinite(ts)) map[symbol] = ts;
    }
    return sanitizePendingPredictionMap(map);
  } catch {
    return {};
  }
}

function persistPendingPredictionMap(map: Record<string, number>) {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(PENDING_PREDICTIONS_KEY, JSON.stringify(map));
}

const initialPendingMap = loadPendingPredictionMap();
persistPendingPredictionMap(initialPendingMap);

export const useAppStore = create<AppState>((set) => ({
  selectedSymbol: null,
  sidebarOpen: true,
  activeSignalType: null,
  pageContext: "Dashboard",
  chatOpen: false,
  chatStreaming: false,
  chatToolStatus: null,
  sseConnected: false,
  pendingPredictions: new Set(Object.keys(initialPendingMap)),
  pendingPredictionStartedAt: initialPendingMap,
  chatMessages: [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hey there -- I'm Linky, your market intelligence assistant. Ask me about any ticker, signal, or prediction and I'll dig into what we know.",
      timestamp: new Date(),
    },
  ],
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setActiveSignalType: (type) => set({ activeSignalType: type }),
  toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
  setChatOpen: (open) => set({ chatOpen: open }),
  addChatMessage: (msg) =>
    set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
  setPageContext: (ctx) => set({ pageContext: ctx }),
  setSSEConnected: (connected) => set({ sseConnected: connected }),
  setChatStreaming: (streaming) =>
    set({ chatStreaming: streaming, chatToolStatus: streaming ? null : null }),
  setChatToolStatus: (tool) => set({ chatToolStatus: tool }),
  addPendingPrediction: (symbol, startedAt) =>
    set((s) => {
      const nextMap = sanitizePendingPredictionMap({
        ...s.pendingPredictionStartedAt,
        [symbol]: startedAt ?? Date.now(),
      });
      persistPendingPredictionMap(nextMap);
      return {
        pendingPredictions: new Set(Object.keys(nextMap)),
        pendingPredictionStartedAt: nextMap,
      };
    }),
  removePendingPrediction: (symbol) =>
    set((s) => {
      const nextMap = { ...s.pendingPredictionStartedAt };
      delete nextMap[symbol];
      const cleaned = sanitizePendingPredictionMap(nextMap);
      persistPendingPredictionMap(cleaned);
      return {
        pendingPredictions: new Set(Object.keys(cleaned)),
        pendingPredictionStartedAt: cleaned,
      };
    }),
  pruneStalePendingPredictions: () =>
    set((s) => {
      const cleaned = sanitizePendingPredictionMap(s.pendingPredictionStartedAt);
      persistPendingPredictionMap(cleaned);
      return {
        pendingPredictions: new Set(Object.keys(cleaned)),
        pendingPredictionStartedAt: cleaned,
      };
    }),
}));
