import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "../../api/client";

interface Row {
  code: string;
  title: string;
  status: string;
  priority_level: string;
  priority_score: number;
  report_count: number;
  ward?: string | null;
  assigned_department_name?: string | null;
  last_reported_at: string;
}

const STATUS_FILTERS = ["", "action_required", "assigned", "in_progress", "verification_pending", "verified", "closed"];

export default function Problems() {
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    API.get("/problems", {
      params: { page, page_size: 20, status: status || undefined, q: q || undefined },
    })
      .then((r) => {
        setRows(r.data.items);
        setTotal(r.data.total);
      })
      .finally(() => setLoading(false));
  }, [page, status, q]);

  useEffect(load, [load]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="display text-2xl font-bold">All problems</h1>
          <p className="text-sm text-slate-500">{total} clusters on record</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input className="input max-w-64" placeholder="Search title / code / area…"
                 value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((s) => (
          <button key={s || "all"}
                  onClick={() => { setPage(1); setStatus(s); }}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ring-1 transition ${
                    status === s ? "bg-slate-800 text-white ring-slate-800"
                      : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"}`}>
            {s ? s.replaceAll("_", " ") : "all statuses"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="card h-64 animate-pulse" />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                <th className="px-4 py-3 font-semibold">Problem</th>
                <th className="px-4 py-3 font-semibold">Priority</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Department</th>
                <th className="px-4 py-3 font-semibold">Reports</th>
                <th className="px-4 py-3 font-semibold">Last activity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((r) => (
                <tr key={r.code} className="transition hover:bg-indigo-50/40">
                  <td className="max-w-72 px-4 py-3">
                    <Link to={`/console/problems/${r.code}`}
                          className="font-semibold text-slate-800 hover:text-indigo-600">
                      {r.title}
                    </Link>
                    <div className="text-xs text-slate-400">{r.code}{r.ward ? ` · Ward ${r.ward}` : ""}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold uppercase ${
                      r.priority_level === "critical" ? "bg-red-100 text-red-700"
                      : r.priority_level === "high" ? "bg-orange-100 text-orange-700"
                      : r.priority_level === "medium" ? "bg-amber-100 text-amber-800"
                      : "bg-slate-100 text-slate-500"}`}>
                      {r.priority_level} {Math.round(r.priority_score)}
                    </span>
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-600">{r.status.replaceAll("_", " ")}</td>
                  <td className="px-4 py-3 text-slate-500">{r.assigned_department_name ?? "—"}</td>
                  <td className="px-4 py-3 font-semibold">{r.report_count}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {new Date(r.last_reported_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn-ghost ring-1 ring-slate-300">← Prev</button>
          <button disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)} className="btn-ghost ring-1 ring-slate-300">Next →</button>
        </div>
      </div>
    </div>
  );
}
