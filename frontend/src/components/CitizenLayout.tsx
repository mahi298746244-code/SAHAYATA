import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NotificationBell from "./NotificationBell";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 via-indigo-500 to-emerald-500 text-white shadow-md"
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 24 24" fill="none" width={size * 0.62} height={size * 0.62}>
        <path
          d="M12 21s-7-4.35-7-10a4 4 0 0 1 7-2.65A4 4 0 0 1 19 11c0 5.65-7 10-7 10Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path d="M8 12h2l1.5-3 1.5 5L14.5 11H17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

const tabs = [
  { to: "/app", label: "Home", icon: "🏠", end: true },
  { to: "/app/report", label: "Report", icon: "➕" },
  { to: "/app/reports", label: "My Reports", icon: "📋" },
  { to: "/app/map", label: "Map", icon: "🗺️" },
];

export default function CitizenLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3">
          <NavLink to="/app" className="flex items-center gap-2.5">
            <Logo />
            <div>
              <div className="display text-lg font-bold leading-none">SAHAYATA</div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Citizen Support
              </div>
            </div>
          </NavLink>
          <nav className="hidden items-center gap-1 md:flex">
            {tabs.slice(1).map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) =>
                  `rounded-xl px-3 py-2 text-sm font-medium ${
                    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50"
                  }`
                }
              >
                {t.icon} {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <NotificationBell basePath="/app" />
            <div className="hidden text-right sm:block">
              <div className="text-sm font-semibold leading-tight">{user?.full_name}</div>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Sign out
              </button>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-700">
              {user?.full_name?.[0]?.toUpperCase() ?? "?"}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-5 md:pb-10">
        <Outlet />
      </main>

      {/* mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white/95 backdrop-blur md:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
                isActive ? "text-indigo-600" : "text-slate-500"
              }`
            }
          >
            <span className="text-lg">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
