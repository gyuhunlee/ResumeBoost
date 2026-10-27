import { NavLink, Outlet } from "react-router";
import Logo from "./Logo";
import {
  BriefcaseIcon,
  DashboardIcon,
  SearchIcon,
  SettingsIcon,
  SparkleIcon,
} from "./Icons";
import type { ComponentType, SVGProps } from "react";
import { useAuth } from "../auth/AuthProvider";

type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
};

// /research doesn't have a page yet; add its route in App.tsx.
const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: DashboardIcon },
  { to: "/applications", label: "Applications", icon: BriefcaseIcon },
  { to: "/tailor", label: "Tailor resume", icon: SparkleIcon },
  { to: "/research", label: "Company research", icon: SearchIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function AppLayout() {
  const { session, signOut } = useAuth();
  const meta = session?.user.user_metadata ?? {};

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

        <div className="mt-auto flex items-center gap-3 rounded-xl border border-slate-200 p-3">
          {meta.avatar_url && <img src={meta.avatar_url} alt="" className="h-8 w-8 rounded-full" referrerPolicy="no-referrer" />}
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{meta.full_name ?? "Account"}</div>
            <div className="truncate text-xs text-slate-500">{session?.user.email}</div>
          </div>
          <button type="button" onClick={signOut} className="min-h-11 cursor-pointer text-sm font-semibold text-blue-700">Sign out</button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-6 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
