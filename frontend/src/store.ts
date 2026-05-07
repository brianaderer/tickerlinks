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
  setSelectedSymbol: (symbol: string | null) => void;
  toggleSidebar: () => void;
  setActiveSignalType: (type: string | null) => void;
  toggleChat: () => void;
  setChatOpen: (open: boolean) => void;
  addChatMessage: (msg: ChatMessage) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedSymbol: null,
  sidebarOpen: true,
  activeSignalType: null,
  chatOpen: false,
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
}));
