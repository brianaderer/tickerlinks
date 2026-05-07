import { Link, useLocation } from "@tanstack/react-router";
import { useAppStore } from "../store";
import {
  HiOutlineHome,
  HiOutlineBuildingOffice2,
  HiOutlineBolt,
  HiOutlineChartBar,
  HiOutlineNewspaper,
  HiOutlineDocumentText,
} from "react-icons/hi2";

const NAV = [
  { to: "/", label: "Front Page", icon: HiOutlineHome },
  { to: "/companies", label: "Companies", icon: HiOutlineBuildingOffice2 },
  { to: "/signals", label: "Signals", icon: HiOutlineBolt },
  { to: "/predictions", label: "Predictions", icon: HiOutlineChartBar },
  { to: "/articles", label: "Articles", icon: HiOutlineNewspaper },
  { to: "/reports", label: "Reports", icon: HiOutlineDocumentText },
] as const;

export default function Sidebar() {
  const open = useAppStore((s) => s.sidebarOpen);
  const location = useLocation();

  return (
    <aside
      className={`fixed top-0 left-0 z-40 h-screen bg-stone-50 border-r border-stone-300 transition-all duration-200 ${open ? "w-56" : "w-16"}`}
    >
      <div className="flex items-center gap-2 px-4 h-14 border-b-2 border-stone-900">
        <span className="font-serif text-stone-900 font-black text-lg tracking-tight">TL</span>
        {open && <span className="font-serif text-stone-900 font-bold text-sm tracking-tight">TickerLinks</span>}
      </div>

      <nav className="mt-4 flex flex-col gap-0.5 px-2">
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to || (to !== "/" && location.pathname.startsWith(to));
          return (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-3 px-3 py-2 rounded text-sm font-sans transition-colors ${
                active
                  ? "bg-stone-900 text-stone-50 font-medium"
                  : "text-stone-600 hover:bg-stone-200 hover:text-stone-900"
              }`}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {open && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
