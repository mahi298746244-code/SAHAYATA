import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "../../api/client";
import type { ActionItem } from "../../api/types";
import { StatusBadge } from "../../components/Badges";

const FLOW = ["assigned", "in_progress", "completed", "verification_pending", "closed"];
const NEXT_LABEL: Record<string, string> = {
  assigned: "▶ Start work",
  in_progress: "✓ Mark completed",
  completed: "→ Send for verification",
  verification_pending: "✔ Close case",
};

export default function ActionsBoard() {
  const [rows, setRows] = useState<ActionItem[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    API.get("/actions", { params: { status: status || undefined, page_size: 50 } })
      .then((r) => setRows(r.data.items))
      .finally(() => setLoading(false));
  }, [status]);

  useEffect(load, [load]);

  async function advance(a: ActionItem) {
    const next =
      a.status === "assigned" ? "in_progress"
      : a.status === "in_progress" ? "completed"
      : a.status === "completed" ? "verification_pending"
      : a.status === "verification_pending" ? "closed" : null;
    if (!next) return;
    setBusy(a.code);
    try {
      if (next === "completed") {
        await API.post(`/actions/${a.code}/evidence`, {
          note: `Work marked complete by console on ${new Date().toLocaleDateString()}.`,
        });
      } else {
        await API.patch(`/actions/${a.code}`, { status: next });
      }
      load();
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Transition failed");
    } finally {
      setBusy("");
    }
  }

  async function reopen(a: ActionItem) {
    setBusy(a.code);
    try {
      await API.patch(`/actions/${a.code}`, { status: "reopened", reason: "reopened from console" });
      load();
    } finally {
      setBusy("");
    }
  }

  const stageIndex = (s: string) => Math.max(0, FLOW.indexOf(s));

  return (
    <div className="space-y-5">
      <div>
        <h1 className="display text-2xl font-bold">Actions board</h1>
        <p className="text-sm text-slate-500">Every work order, tracked from assignment to verified closure.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {["", ...FLOW, "reopened", "cancelled"].map((s) => (
          <button key={s || "all"} onClick={() => setStatus(s)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ring-1 transition ${
                    status === s ? "bg-slate-800 text-white ring-slate-800"
                      : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"}`}>
            {s ? s.replaceAll("_", " ") : "all"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="card h-64 animate-pulse" />
      ) : rows.length === 0 ? (
        <div className="card p-12 text-center text-sm text-slate-400">No work orders here.</div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {rows.map((a) => (
            <div key={a.code} className="card p-5">
              <div className="flex items-center justify-between gap-2">
                <Link to={`/console/problems/${a.cluster?.code ?? ""}`}
                      className="truncate font-semibold text-slate-800 hover:text-indigo-600">
                  {a.cluster?.title ?? a.cluster_id}
                </Link>
                <StatusBadge status={a.status} />
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {a.code} · {a.department?.name ?? "—"}{a.team_name ? ` · ${a.team_name}` : ""}
              </div>

              {/* progress rail */}
              <div className="mt-4 flex items-center gap-1">
                {FLOW.map((s, i) => (
                  <div key={s} className="flex flex-1 flex-col items-center gap-1">
                    <div className={`h-1.5 w-full rounded-full ${
                      i <= stageIndex(a.status) ? "bg-indigo-500" : "bg-slate-200"}`} />
                    <span className={`text-[9px] font-semibold uppercase ${
                      i <= stageIndex(a.status) ? "text-indigo-600" : "text-slate-300"}`}>
                      {s.split("_")[0]}
                    </span>
                  </div>
                ))}
              </div>

              {a.notes && <p className="mt-3 line-clamp-2 text-sm text-slate-500">{a.notes}</p>}
              {typeof a.estimated_cost === "number" && a.estimated_cost > 0 && (
                <p className="mt-1 text-xs text-slate-400">Est. cost ₹{a.estimated_cost.toLocaleString()}</p>
              )}

              <div className="mt-4 flex gap-2">
                {NEXT_LABEL[a.status] && (
                  <button disabled={busy === a.code} onClick={() => advance(a)} className="btn-primary !py-2">
                    {NEXT_LABEL[a.status]}
                  </button>
                )}
                {!["closed", "cancelled"].includes(a.status) && a.status !== "reopened" && (
                  <button disabled={busy === a.code} onClick={() => reopen(a)}
                          className="btn-ghost !py-2 text-orange-600 ring-1 ring-orange-200">
                    ↩ Reopen
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
