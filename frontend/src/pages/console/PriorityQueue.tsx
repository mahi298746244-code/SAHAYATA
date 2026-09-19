import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "../../api/client";
import type { ProblemCluster } from "../../api/types";
import { LevelBadge, StatusBadge } from "../../components/Badges";

interface Overview {
  total_reports: number;
  critical_issues: number;
  action_required: number;
  resolved: number;
  active_problems: number;
  new_reports_7d: number;
}

export default function PriorityQueue() {
  const [items, setItems] = useState<ProblemCluster[]>([]);
  const [ov, setOv] = useState<Overview | null>(null);
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.get("/analytics/overview").then((r) => setOv(r.data));
  }, []);

  useEffect(() => {
    setLoading(true);
    API.get("/priorities", { params: { limit: 50, level: level || undefined } })
      .then((r) => setItems(r.data))
      .finally(() => setLoading(false));
  }, [level]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-2xl font-bold">Priority queue</h1>
        <p className="text-sm text-slate-500">
          Ranked by the transparent formula — severity × scale × vulnerability × neglect time.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Mini label="Critical now" value={ov?.critical_issues} tone="bg-red-50 text-red-700" />
        <Mini label="Awaiting assignment" value={ov?.action_required} tone="bg-amber-50 text-amber-700" />
        <Mini label="Verified resolved" value={ov?.resolved} tone="bg-emerald-50 text-emerald-700" />
        <Mini label="Reports last 7d" value={ov?.new_reports_7d} tone="bg-indigo-50 text-indigo-700" />
      </div>

      <div className="flex flex-wrap gap-2">
        {["", "critical", "high", "medium", "low"].map((l) => (
          <button key={l || "all"} onClick={() => setLevel(l)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold uppercase ring-1 transition ${
                    level === l ? "bg-slate-800 text-white ring-slate-800"
                      : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
                  }`}>
            {l || "all levels"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="card h-64 animate-pulse" />
      ) : items.length === 0 ? (
        <div className="card p-12 text-center text-sm text-slate-400">Queue is clear. 🎉</div>
      ) : (
        <div className="card divide-y divide-slate-100">
          {items.map((p, i) => (
            <Link key={p.code}
                  to={`/console/problems/${p.code}`}
                  className="flex items-center gap-4 px-5 py-4 transition hover:bg-indigo-50/40">
              <div className={`display w-10 shrink-0 text-center text-lg font-extrabold ${
                i === 0 ? "text-red-500" : i < 3 ? "text-orange-500" : "text-slate-300"}`}>
                {i + 1}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-semibold text-slate-800">{p.title}</span>
                  <LevelBadge level={p.level ?? p.priority_level} />
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-slate-400">
                  <span>{p.code}</span>
                  <span className="capitalize">{(p.category as string) ?? "—"}</span>
                  <span>👥 {p.report_count} report(s) · ~{p.affected_population_est ?? 0} people</span>
                </div>
                {(p.top_factors ?? []).length > 0 && (
                  <div className="mt-1 truncate text-[11px] text-emerald-700">
                    ⚖️ {p.top_factors?.join(" · ")}
                  </div>
                )}
              </div>
              <StatusBadge status={p.status} />
              <div className="text-right">
                <div className="display text-xl font-extrabold text-slate-700">
                  {Math.round(p.score ?? p.priority_score ?? 0)}
                </div>
                <div className="text-[10px] font-bold uppercase tracking-wide text-slate-300">score</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Mini({ label, value, tone }: { label: string; value?: number; tone: string }) {
  return (
    <div className={`rounded-2xl p-4 ${tone}`}>
      <div className="display text-2xl font-extrabold">{value ?? "—"}</div>
      <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide opacity-70">{label}</div>
    </div>
  );
}
