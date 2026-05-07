import { useEffect } from "react";
import { Outlet, useRouterState } from "@tanstack/react-router";
import Sidebar from "./Sidebar";
import ChatDrawer from "./ChatDrawer";
import { useAppStore } from "../store";
import { HiOutlineBars3 } from "react-icons/hi2";
import { useSSE } from "../api/sse";

export default function Layout() {
  useSSE();
  const location = useRouterState({ select: (s) => s.location });
  const setPageContext = useAppStore((s) => s.setPageContext);
  useEffect(() => {
    setPageContext(location.pathname);
  }, [location.pathname, setPageContext]);
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const sseConnected = useAppStore((s) => s.sseConnected);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 font-sans">
      <Sidebar />
      <div className={`transition-all duration-200 ${sidebarOpen ? "ml-56" : "ml-16"}`}>
        <header className="sticky top-0 z-30 bg-stone-50/90 backdrop-blur">
          <div className="flex items-center justify-between px-6 h-14">
            <button onClick={toggleSidebar} className="text-stone-400 hover:text-stone-700">
              <HiOutlineBars3 className="w-5 h-5" />
            </button>
            <div className="text-center">
              <h1 className="font-serif font-black text-2xl tracking-tight text-stone-900">TickerLinks</h1>
            </div>
            <div className="flex items-center gap-3">
              <span className={`w-1.5 h-1.5 rounded-full ${sseConnected ? "bg-emerald-500" : "bg-red-500"}`} title={sseConnected ? "Live" : "Disconnected"} />
              <span className="text-xs text-stone-400 font-sans">{today}</span>
            </div>
          </div>
          <div className="mx-6">
            <div className="h-px bg-stone-900" />
            <div className="h-[3px] bg-stone-900 mt-px" />
          </div>
        </header>
        <main className="px-6 py-8 max-w-7xl mx-auto">
          <Outlet />
        </main>
      </div>
      <ChatDrawer />
    </div>
  );
}
