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
  addPendingPrediction: (symbol: string) => void;
  removePendingPrediction: (symbol: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedSymbol: null,
  sidebarOpen: true,
  activeSignalType: null,
  pageContext: "Dashboard",
  chatOpen: false,
  chatStreaming: false,
  chatToolStatus: null,
  sseConnected: false,
  pendingPredictions: new Set(),
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
  addPendingPrediction: (symbol) =>
    set((s) => ({ pendingPredictions: new Set([...s.pendingPredictions, symbol]) })),
  removePendingPrediction: (symbol) =>
    set((s) => {
      const next = new Set(s.pendingPredictions);
      next.delete(symbol);
      return { pendingPredictions: next };
    }),
}));
