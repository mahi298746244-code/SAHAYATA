import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { API } from "../api/client";
import type { ActionItem, ReportOut } from "../api/types";
import { LevelBadge, SeverityDots, StatusBadge } from "../components/Badges";
import MapCanvas from "../components/MapCanvas";
import MediaGallery from "../components/MediaGallery";
import { useAuth } from "../context/AuthContext";

interface Detail {
  code: string;
  title: string;
  status: string;
  category_name?: string | null;
  subcategory?: string | null;
  priority_score: number;
  priority_level: string;
  priority_components?: {
    components?: Record<string, { contribution: number; value?: number; detail?: string }>;
  };
  report_count: number;
  affected_population_est?: number;
  ward?: string | null;
  address_text?: string | null;
  latitude: number;
  longitude: number;
  assigned_department_name?: string | null;
  first_reported_at: string;
  last_reported_at?: string;
  reports: ReportOut[];
  actions: ActionItem[];
}

interface Dept {
  id: string;
  name: string;
}

function fmtDate(s?: string) {
  return s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export default function ProblemDetail({ staff = false }: { staff?: boolean }) {
  const { code } = useParams();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { reportCode?: string; created?: string } };
  const { user } = useAuth();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [depts, setDepts] = useState<Dept[]>([]);
  const [deptId, setDeptId] = useState("");
  const [teamName, setTeamName] = useState("");
  const [notes, setNotes] = useState("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [openReport, setOpenReport] = useState<string | null>(loc.state?.reportCode ?? null);
  const [mediaFor, setMediaFor] = useState<Record<string, unknown[]>>({});
  const [verdictMsg, setVerdictMsg] = useState("");

  const load = useCallback(() => {
    API.get(`/problems/${code}`)
      .then((r) => {
        setD(r.data);
        setDeptId(r.data.assigned_department_id ?? "");
      })
      .catch((e) => setErr(e?.response?.data?.detail ?? "Problem not found"));
  }, [code]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!staff) return;
    API.get("/catalog/departments").then((r) => setDepts(r.data));
  }, [staff]);

  async function toggleMedia(r: ReportOut) {
    setOpenReport(openReport === r.code ? null : r.code);
    if (!mediaFor[r.code]) {
      const embedded = (r as unknown as { media?: unknown[] }).media;
      if (embedded?.length) {
        setMediaFor((m) => ({ ...m, [r.code]: embedded }));
        return;
      }
      const det = await API.get(`/reports/${r.code}`).catch(() => null);
      if (det) setMediaFor((m) => ({ ...m, [r.code]: det.data.media ?? [] }));
    }
  }

  async function createAction() {
    if (!d) return;
    setBusy(true);
    try {
      await API.post("/actions", {
        problem_id: d.code,
        department_id: deptId,
        team_name: teamName || undefined,
        notes: notes || undefined,
      });
      setTeamName("");
      setNotes("");
      load();
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to create action");
    } finally {
      setBusy(false);
    }
  }

  async function transition(actionCode: string, status: string) {
    setBusy(true);
    try {
      await API.patch(`/actions/${actionCode}`, { status, notes: notes || undefined });
      load();
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Transition failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitEvidence(actionCode: string) {
    setBusy(true);
    try {
      await API.post(`/actions/${actionCode}/evidence`, { note: evidenceNote });
      setEvidenceNote("");
      load();
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Evidence failed");
    } finally {
      setBusy(false);
    }
  }

  async function verify(verdict: string) {
    if (!d) return;
    setBusy(true);
    try {
      await API.post("/verifications", { problem_id: d.code, verdict });
      setVerdictMsg(verdict === "yes" ? "✅ Thank you! Case marked verified." :
        verdict === "no" ? "↩️ Noted — the problem is back with the department." : "📝 Partial verification recorded.");
      load();
    } catch (e: unknown) {
      setErr((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  if (err && !d)
    return (
      <div className="card mx-auto max-w-lg p-10 text-center">
        <div className="text-4xl">🔍</div>
        <p className="mt-3 text-sm text-slate-500">{err}</p>
        <button onClick={() => nav(-1)} className="btn-primary mt-5">Go back</button>
      </div>
    );
  if (!d) return <div className="card h-64 animate-pulse" />;

  const latestAction = d.actions[d.actions.length - 1];
  const canVerify = !staff && user?.role === "citizen" && d.status === "verification_pending";

  return (
    <div className="space-y-6">
      {(loc.state?.created || loc.state?.reportCode) && (
        <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700 ring-1 ring-emerald-200">
          🎉 {loc.state.created
            ? `Report ${loc.state.created} submitted — it joined this problem cluster.`
            : `Viewing your report ${loc.state.reportCode}.`}
        </div>
      )}

      {/* Header */}
      <div className="card overflow-hidden">
        <div className={`px-6 py-5 text-white ${
          d.priority_level === "critical" ? "bg-gradient-to-r from-red-600 to-orange-500"
          : d.priority_level === "high" ? "bg-gradient-to-r from-orange-500 to-amber-500"
          : d.priority_level === "low" ? "bg-gradient-to-r from-slate-500 to-slate-400"
          : "bg-gradient-to-r from-indigo-600 to-violet-500"}`}>
          <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider opacity-80">
            <span>{d.code}</span> · <LevelBadge level={d.priority_level} />
          </div>
          <h1 className="display mt-1 text-2xl font-extrabold">{d.title}</h1>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs opacity-90">
            <span>🏷️ {d.category_name ?? "Uncategorised"}{d.subcategory ? ` · ${d.subcategory}` : ""}</span>
            <span>👥 ~{d.report_count} report(s) · est. {d.affected_population_est ?? 0} people affected</span>
            <span>📍 {d.address_text ?? d.ward ?? "Map location"}</span>
            <span>⏱️ First seen {fmtDate(d.first_reported_at)}</span>
          </div>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-2">
          <div>
            <div className="label">Status</div>
            <StatusBadge status={d.status} />
            {d.assigned_department_name && (
              <p className="mt-2 text-sm text-slate-600">
                Handled by <b>{d.assigned_department_name}</b>
              </p>
            )}
            {canVerify && (
              <div className="mt-4 rounded-xl bg-purple-50 p-4 ring-1 ring-purple-200">
                <div className="text-sm font-bold text-purple-900">Did the department actually fix this?</div>
                <p className="mt-1 text-xs text-purple-700">Your answer keeps everyone honest.</p>
                <div className="mt-3 flex gap-2">
                  <button disabled={busy} onClick={() => verify("yes")}
                          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
                    ✅ Yes, resolved
                  </button>
                  <button disabled={busy} onClick={() => verify("no")}
                          className="rounded-xl bg-red-100 px-4 py-2 text-sm font-semibold text-red-700 ring-1 ring-red-300 hover:bg-red-200 disabled:opacity-50">
                    ❌ No, still broken
                  </button>
                  <button disabled={busy} onClick={() => verify("partial")}
                          className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-50">
                    🤷 Partially
                  </button>
                </div>
                {verdictMsg && <p className="mt-2 text-xs font-semibold text-purple-800">{verdictMsg}</p>}
              </div>
            )}
          </div>
          <MapCanvas points={[{ id: d.code, type: "problem", lat: d.latitude, lng: d.longitude,
                                title: d.title, priority_level: d.priority_level, report_count: d.report_count,
                                status: d.status }]}
                     center={[d.latitude, d.longitude]} zoom={16} height="220px" />
        </div>
      </div>

      {/* Priority breakdown */}
      <div className="card p-6">
        <h2 className="display mb-1 text-lg font-bold">
          Why is this ranked {Math.round(d.priority_score)}/100?
        </h2>
        <p className="mb-4 text-xs text-slate-400">Transparent formula — every factor is shown.</p>
        <div className="space-y-2.5">
          {Object.entries(d.priority_components?.components ?? {}).map(([k, comp]) => (
            <div key={k}>
              <div className="flex justify-between text-xs font-medium capitalize text-slate-600">
                <span>{k.replace(/_/g, " ")}</span>
                <span>+{comp.contribution.toFixed(0)} pts</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-emerald-400"
                     style={{ width: `${Math.min(100, comp.contribution)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Staff workflow panel */}
      {staff && (
        <div className="card space-y-4 p-6">
          <h2 className="display text-lg font-bold">Officer actions</h2>
          {!latestAction || ["closed", "cancelled"].includes(latestAction.status) ? (
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <select className="input" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
                <option value="">Select department…</option>
                {depts.map((dep) => <option key={dep.id} value={dep.id}>{dep.name}</option>)}
              </select>
              <input className="input" placeholder="Team name (optional)" value={teamName}
                     onChange={(e) => setTeamName(e.target.value)} />
              <button className="btn-primary" disabled={!deptId || busy}
                      onClick={() => latestAction ? transition(latestAction.code, "in_progress") : createAction()}>
                {latestAction ? "▶ Reopen work" : "🛠️ Assign & create action"}
              </button>
              <textarea className="input sm:col-span-3" placeholder="Work notes…" rows={2}
                        value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <span className="text-sm font-semibold">{latestAction.code}</span>
                <StatusBadge status={latestAction.status} />
                <span className="text-xs text-slate-500">{latestAction.department?.name}</span>
                <div className="ml-auto flex flex-wrap gap-2">
                  {latestAction.status === "assigned" && (
                    <button disabled={busy} onClick={() => transition(latestAction.code, "in_progress")}
                            className="btn-primary !py-2">▶ Start work</button>
                  )}
                  {["in_progress", "verification_pending"].includes(latestAction.status) && (
                    <>
                      <input className="input max-w-56" placeholder="Resolution note…" value={evidenceNote}
                             onChange={(e) => setEvidenceNote(e.target.value)} />
                      <button disabled={busy || evidenceNote.trim().length < 4}
                              onClick={() => submitEvidence(latestAction.code)}
                              className="btn-primary !py-2">📸 Submit resolution</button>
                    </>
                  )}
                  {latestAction.status === "verification_pending" && (
                    <button disabled={busy} onClick={() => transition(latestAction.code, "closed")}
                            className="btn-ghost !py-2 text-emerald-700">✔ Close without citizen</button>
                  )}
                  {latestAction.status !== "in_progress" && (
                    <button disabled={busy} onClick={() => transition(latestAction.code, "reopened")}
                            className="btn-ghost !py-2 text-orange-600">↩ Reopen</button>
                  )}
                </div>
              </div>
              <textarea className="input" placeholder="Additional notes…" rows={2}
                        value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          )}
        </div>
      )}

      {/* Citizen reports in this cluster */}
      <div className="card p-6">
        <h2 className="display mb-1 text-lg font-bold">
          Citizen reports ({d.reports.length})
        </h2>
        <p className="mb-4 text-xs text-slate-400">
          Multiple citizens reported the same issue — merged into one problem so it gets fixed once.
        </p>
        <ul className="divide-y divide-slate-100">
          {d.reports.map((r) => (
            <li key={r.code} className="py-3">
              <button className="flex w-full items-center gap-3 text-left" onClick={() => toggleMedia(r)}>
                <SeverityDots value={r.ai_severity} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{r.title}</div>
                  <div className="text-xs text-slate-400">{r.code} · {fmtDate(r.created_at)}</div>
                </div>
                <StatusBadge status={r.status} />
                <span className="text-slate-300">{openReport === r.code ? "▴" : "▾"}</span>
              </button>
              {openReport === r.code && (
                <div className="mt-3 space-y-3 rounded-xl bg-slate-50 p-4">
                  {r.description && <p className="text-sm text-slate-600">{r.description}</p>}
                  {r.landmark && <p className="text-xs text-slate-400">Landmark: {r.landmark}</p>}
                  {r.ai_keywords?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {r.ai_keywords.map((k) => (
                        <span key={k} className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-600">{k}</span>
                      ))}
                    </div>
                  ) : null}
                  <MediaGallery media={(mediaFor[r.code] ?? []) as never} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Action history */}
      {d.actions.length > 0 && (
        <div className="card p-6">
          <h2 className="display mb-4 text-lg font-bold">Work history</h2>
          <ol className="relative space-y-4 border-l border-slate-200 pl-5">
            {d.actions.map((a) => (
              <li key={a.code}>
                <span className="absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-indigo-500 ring-1 ring-indigo-200" />
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-sm">{a.code}</b>
                  <StatusBadge status={a.status} />
                  <span className="text-xs text-slate-400">{fmtDate(a.created_at)}</span>
                </div>
                {a.team_name && <div className="mt-0.5 text-xs text-slate-500">Team: {a.team_name} · {a.department?.name}</div>}
                {a.notes && <p className="mt-1 text-sm text-slate-600">{a.notes}</p>}
                {typeof a.estimated_cost === "number" && a.estimated_cost > 0 && (
                  <div className="mt-0.5 text-xs text-slate-400">Est. cost ₹{a.estimated_cost.toLocaleString()}</div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {err && (
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">{err}</div>
      )}
    </div>
  );
}
