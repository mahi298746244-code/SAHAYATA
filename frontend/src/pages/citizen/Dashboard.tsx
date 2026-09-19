import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "../../api/client";
import type { ProblemCluster, ReportOut } from "../../api/types";
import { LevelBadge, StatusBadge } from "../../components/Badges";
import { useAuth } from "../../context/AuthContext";

function Stat({ label, value, accent }: { label: string; value: number | string; accent: string }) {
  return (
    <div className="card p-5">
      <div className={`display text-3xl font-extrabold ${accent}`}>{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [ov, setOv] = useState<Record<string, number>>({});
  const [mine, setMine] = useState<ReportOut[]>([]);
  const [nearby, setNearby] = useState<ProblemCluster[]>([]);
  const [ward, setWard] = useState("");

  useEffect(() => {
    API.get("/analytics/overview").then((r) => setOv(r.data));
    API.get("/reports/mine", { params: { page_size: 5 } }).then((r) => {
      setMine(r.data.items);
      const w = r.data.items?.[0]?.ward;
      if (w) setWard(String(w));
    });
  }, []);

  useEffect(() => {
    API.get("/priorities", { params: { limit: 6 } })
      .then((r) => setNearby(r.data))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-700 via-indigo-600 to-emerald-600 p-8 text-white shadow-lg">
        <svg className="absolute -right-10 -top-10 h-64 w-64 opacity-20" viewBox="0 0 100 100" fill="none">
          <circle cx="50" cy="50" r="48" stroke="white" strokeWidth="1" />
          <circle cx="50" cy="50" r="34" stroke="white" strokeWidth="0.7" />
          <circle cx="50" cy="50" r="20" stroke="white" strokeWidth="0.5" />
        </svg>
        <h1 className="display text-2xl font-extrabold sm:text-3xl">
          Namaste, {user?.full_name?.split(" ")[0]} 👋
        </h1>
        <p className="mt-2 max-w-xl text-sm text-indigo-100">
          See a pothole? A broken streetlight? No water for days?
          Report it in under 30 seconds — AI does the paperwork, you track the fix.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link to="/app/report" className="btn-primary !bg-white !text-indigo-700 hover:!bg-indigo-50">
            ➕ Report an issue
          </Link>
          <Link to="/app/map"
                className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-semibold ring-1 ring-white/30 backdrop-blur hover:bg-white/20">
            🗺️ Explore city map
          </Link>
        </div>
      </section>

      {/* City stats */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Total reports" value={ov.total_reports ?? "—"} accent="text-slate-800" />
        <Stat label="Active problems" value={ov.active_problems ?? "—"} accent="text-amber-600" />
        <Stat label="Resolved & verified" value={ov.resolved ?? "—"} accent="text-emerald-600" />
        <Stat label="New this week" value={ov.new_reports_7d ?? "—"} accent="text-indigo-600" />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* My recent reports */}
        <section className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="display text-lg font-bold">My recent reports</h2>
            <Link to="/app/reports" className="text-xs font-semibold text-indigo-600 hover:underline">
              View all →
            </Link>
          </div>
          {mine.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
              Nothing yet — your first report is one tap away. 📸
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {mine.map((r) => (
                <li key={r.code} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    {r.cluster_code ? (
                      <Link to={`/app/problems/${r.cluster_code}`}
                            state={{ reportCode: r.code }}
                            className="truncate text-sm font-semibold text-slate-800 hover:text-indigo-600">
                        {r.title}
                      </Link>
                    ) : (
                      <span className="truncate text-sm font-semibold text-slate-800">{r.title}</span>
                    )}
                    <div className="mt-0.5 text-xs text-slate-400">
                      {r.code} · {r.category_name ?? "Uncategorised"}
                      {r.ward ? ` · Ward ${r.ward}` : ""}
                    </div>
                  </div>
                  <StatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Priority spotlight */}
        <section className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="display text-lg font-bold">What the city is fixing first</h2>
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-bold uppercase text-indigo-600">
              Live priority
            </span>
          </div>
          {nearby.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
              Loading priority queue…
            </div>
          ) : (
            <ul className="space-y-2.5">
              {nearby.slice(0, 5).map((p) => (
                <li key={p.code}
                    className="flex items-center gap-3 rounded-xl bg-slate-50 px-3.5 py-3 ring-1 ring-slate-200/70">
                  <LevelBadge level={p.level ?? p.priority_level} />
                  <Link to={`/app/problems/${p.code}`}
                        className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700 hover:text-indigo-600">
                    {p.title}
                  </Link>
                  <span className="text-xs font-bold text-slate-400">{Math.round(p.score ?? p.priority_score ?? 0)}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
            Ranked transparently by severity × scale × vulnerability × time waiting — no favouritism,
            formula is public.
          </p>
        </section>
      </div>

      {ward && (
        <p className="text-center text-xs text-slate-400">Your ward: {ward}</p>
      )}
    </div>
  );
}
