import { NavLink, Outlet } from "react-router";
import Logo from "./Logo";
import {
  DocIcon,
  GridIcon,
  SearchIcon,
  SettingsIcon,
  SparkleIcon,
} from "./Icons";
import type { ComponentType, SVGProps } from "react";

type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
};

// /resumes, /research and /settings don't have pages yet; add routes in App.tsx.
const NAV: NavItem[] = [
  { to: "/dashboard", label: "Applications", icon: GridIcon },
  { to: "/tailor", label: "Tailor resume", icon: SparkleIcon },
  { to: "/resumes", label: "My resumes", icon: DocIcon },
  { to: "/research", label: "Company research", icon: SearchIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-wrap bg-slate-50">
      <aside className="flex w-full flex-col gap-6 border-b border-slate-200 bg-white px-4 py-5 md:w-60 md:border-r md:border-b-0">
        <div className="px-2">
          <Logo to="/" />
        </div>

        <nav aria-label="App" className="flex flex-row flex-wrap gap-1 md:flex-col">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-lg px-3 text-[15px] no-underline ${
                  isActive
                    ? "bg-blue-50 font-semibold text-blue-700"
                    : "font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto hidden flex-col gap-1.5 rounded-xl border border-slate-200 p-3.5 md:flex">
          <div className="flex items-center gap-2 text-[13px] font-semibold text-green-700">
            <span className="h-2 w-2 rounded-full bg-green-700" />
            Gmail connected
          </div>
          <div className="text-[13px] text-slate-500">Synced 5 min ago</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-6 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
