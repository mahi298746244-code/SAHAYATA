import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { API } from "../../api/client";

const COLORS = ["#4f46e5", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function Analytics() {
  const [full, setFull] = useState<Record<string, unknown>>({});
  const [overview, setOverview] = useState<Record<string, number>>({});

  useEffect(() => {
    API.get("/analytics/overview").then((r) => setOverview(r.data));
    API.get("/analytics/full").then((r) => setFull(r.data)).catch(() => {});
  }, []);

  const trends = (full.trends as { date: string; count: number }[]) ?? [];
  const byCategory = (full.by_category as { name?: string; category?: string; count: number }[]) ?? [];
  const departments = (full.departments as { name: string; total_actions: number }[]) ?? [];
  const verification = (full.verification as Record<string, number>) ?? {};
  const resolution = (full.resolution_time as { avg_resolution_hours?: number }) ?? {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-2xl font-bold">Analytics</h1>
        <p className="text-sm text-slate-500">Live numbers — every figure computed from real reports.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["Total reports", overview.total_reports],
          ["Active problems", overview.active_problems],
          ["Critical open", overview.critical_issues],
          ["Verified resolved", overview.resolved],
          ["New this week", overview.new_reports_7d],
          ["Registered citizens", overview.registered_citizens],
          ["Avg resolution (hrs)", resolution.avg_resolution_hours],
          ["Verification pass rate", verification.success_rate != null ? `${verification.success_rate}%` : undefined],
        ].map(([label, v]) => (
          <div key={String(label)} className="card p-5">
            <div className="display text-2xl font-extrabold text-slate-800">{v ?? "—"}</div>
            <div className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="display mb-4 text-lg font-bold">Reports per day</h2>
          {trends.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d: string) => d.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#4f46e5" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </section>

        <section className="card p-5">
          <h2 className="display mb-4 text-lg font-bold">Problems by category</h2>
          {byCategory.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={byCategory} dataKey="count" nameKey={(k: { name?: string; category?: string }) => k.name ?? k.category ?? "Other"}
                     outerRadius={95} innerRadius={55} paddingAngle={3}>
                  {byCategory.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </section>

        <section className="card p-5 lg:col-span-2">
          <h2 className="display mb-4 text-lg font-bold">Department workload</h2>
          {departments.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={departments}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-18} height={54} dy={12} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="total_actions" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </section>

        <section className="card p-5">
          <h2 className="display mb-4 text-lg font-bold">Citizen verification outcomes</h2>
          <div className="space-y-3 text-sm">
            {[
              ["✅ Confirmed resolved", verification.confirmed, "bg-emerald-500"],
              ["❌ Rejected (reopened)", verification.rejected, "bg-red-500"],
              ["🤷 Partial", verification.partial, "bg-amber-400"],
            ].map(([label, val, color]) => (
              <div key={String(label)}>
                <div className="flex justify-between text-xs font-medium text-slate-600">
                  <span>{label}</span><span>{val ?? 0}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-slate-100">
                  <div className={`h-2 rounded-full ${color}`} style={{
                    width: `${Math.min(100, Number(val ?? 0) / Math.max(1, Number(verification.confirmed ?? 0) + Number(verification.rejected ?? 0) + Number(verification.partial ?? 0)) * 100)}%`}} />
                </div>
              </div>
            ))}
            <p className="rounded-xl bg-indigo-50 p-3 text-xs text-indigo-700">
              Pass rate {verification.success_rate ?? "—"}% — citizens are the final auditors of public work.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

function Empty() {
  return (
    <div className="flex h-60 items-center justify-center text-sm text-slate-300">
      Not enough data yet
    </div>
  );
}
