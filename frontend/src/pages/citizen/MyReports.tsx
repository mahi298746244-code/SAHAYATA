import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "../../api/client";
import type { ReportOut } from "../../api/types";
import { SeverityDots, StatusBadge } from "../../components/Badges";

const STATUS_TABS = [
  ["", "All"],
  ["reported", "New"],
  ["in_progress", "In progress"],
  ["verification_pending", "To verify"],
  ["verified", "Resolved"],
  ["reopened", "Reopened"],
] as const;

export default function MyReports() {
  const [items, setItems] = useState<ReportOut[]>([]);
  const [status, setStatus] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    API.get("/reports/mine", { params: { status: status || undefined, page_size: 50 } })
      .then((r) => {
        setItems(r.data.items);
        setTotal(r.data.total);
      })
      .finally(() => setLoading(false));
  }, [status]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="display text-2xl font-bold">My reports</h1>
          <p className="text-sm text-slate-500">{total} report(s) filed by you</p>
        </div>
        <Link to="/app/report" className="btn-primary">➕ New report</Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map(([val, label]) => (
          <button key={val || "all"} onClick={() => setStatus(val)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ring-1 transition ${
                    status === val
                      ? "bg-slate-800 text-white ring-slate-800"
                      : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
                  }`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-20 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card p-12 text-center text-sm text-slate-400">
          No reports in this filter.
        </div>
      ) : (
        <div className="grid gap-3">
          {items.map((r) => (
            <Link key={r.code}
                  to={r.cluster_code ? `/app/problems/${r.cluster_code}` : "/app/reports"}
                  state={r.cluster_code ? { reportCode: r.code } : undefined}
                  className="card flex items-center gap-4 p-4 transition hover:ring-indigo-300">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-100 to-emerald-100 text-lg">
                  📌
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-slate-800">{r.title}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                    <span>{r.code}</span>
                    <span>{r.category_name ?? "—"}</span>
                    {r.ward && <span>Ward {r.ward}</span>}
                    <SeverityDots value={r.ai_severity} />
                    {typeof r.media_count === "number" && r.media_count > 0 && (
                      <span>📎 {r.media_count}</span>
                    )}
                  </div>
                </div>
                <StatusBadge status={r.status} />
              </Link>
          ))}
        </div>
      )}
    </div>
  );
}
