import { create } from "zustand";

interface AppState {
  selectedSymbol: string | null;
  sidebarOpen: boolean;
  activeSignalType: string | null;
  setSelectedSymbol: (symbol: string | null) => void;
  toggleSidebar: () => void;
  setActiveSignalType: (type: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedSymbol: null,
  sidebarOpen: true,
  activeSignalType: null,
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setActiveSignalType: (type) => set({ activeSignalType: type }),
}));
