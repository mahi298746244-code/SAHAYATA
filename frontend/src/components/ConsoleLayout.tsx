import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "./CitizenLayout";
import NotificationBell from "./NotificationBell";

const nav = [
  { to: "/console", label: "Priority Queue", icon: "🎯", end: true },
  { to: "/console/problems", label: "Problems", icon: "🗂️" },
  { to: "/console/actions", label: "Actions", icon: "🛠️" },
  { to: "/console/map", label: "Map", icon: "🗺️" },
  { to: "/console/analytics", label: "Analytics", icon: "📊" },
  { to: "/console/simulator", label: "Simulator", icon: "🧪" },
];

export default function ConsoleLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-full">
      <aside className="fixed hidden h-full w-60 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <Logo size={28} />
          <div>
            <div className="display text-base font-bold leading-tight">SAHAYATA</div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-indigo-600">
              Officer Console
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              <span>{n.icon}</span> {n.label}
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <NavLink
              to="/admin/users"
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${
                  isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              <span>👥</span> Users & Admin
            </NavLink>
          )}
        </nav>
        <div className="border-t border-slate-100 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{user?.full_name}</div>
              <div className="text-xs text-slate-500 capitalize">{user?.role}</div>
            </div>
            <NotificationBell basePath="/console" />
          </div>
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="btn-ghost w-full justify-start"
          >
            ⏻ Sign out
          </button>
        </div>
      </aside>

      <div className="ml-0 flex min-h-full w-full flex-col md:ml-60">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur md:hidden">
          <NavLink to="/console" className="flex items-center gap-2">
            <Logo size={26} />
            <span className="display font-bold">SAHAYATA</span>
          </NavLink>
          <select
            className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value=""
            onChange={(e) => e.target.value && navigate(e.target.value)}
          >
            <option value="" disabled>
              Go to…
            </option>
            {nav.map((n) => (
              <option key={n.to} value={n.to}>
                {n.icon} {n.label}
              </option>
            ))}
            {user?.role === "admin" && <option value="/admin/users">👥 Users</option>}
          </select>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
