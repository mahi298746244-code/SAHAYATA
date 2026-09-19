import { useCallback, useEffect, useState } from "react";
import { API } from "../../api/client";

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  department_id?: string | null;
  department_name?: string | null;
  ward?: string | null;
  is_active: boolean;
}

interface Dept {
  id: string;
  name: string;
}

export default function AdminUsers() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [depts, setDepts] = useState<Dept[]>([]);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    API.get("/admin/users", { params: { q: q || undefined, role: role || undefined } })
      .then((r) => setRows(r.data.items ?? r.data));
  }, [q, role]);

  useEffect(() => {
    load();
    API.get("/catalog/departments").then((r) => setDepts(r.data));
  }, [load]);

  async function patch(id: string, payload: Record<string, unknown>) {
    await API.patch(`/admin/users/${id}`, payload);
    setMsg("Saved ✓");
    setTimeout(() => setMsg(""), 1500);
    load();
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="display text-2xl font-bold">Users & access</h1>
          <p className="text-sm text-slate-500">Promote officers, deactivate accounts, assign departments.</p>
        </div>
        {msg && <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">{msg}</span>}
      </div>

      <div className="flex flex-wrap gap-2">
        <input className="input max-w-64" placeholder="Search name / email…"
               value={q} onChange={(e) => setQ(e.target.value)} />
        {["", "citizen", "authority", "admin"].map((r) => (
          <button key={r || "all"} onClick={() => setRole(r)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ring-1 ${
                    role === r ? "bg-slate-800 text-white ring-slate-800" : "bg-white text-slate-600 ring-slate-300"}`}>
            {r || "all roles"}
          </button>
        ))}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Department</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {rows.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3">
                  <div className="font-semibold text-slate-800">{u.full_name}</div>
                  <div className="text-xs text-slate-400">{u.email}{u.ward ? ` · ${u.ward}` : ""}</div>
                </td>
                <td className="px-4 py-3">
                  <select className="input !w-36 !py-1.5 text-xs" value={u.role} disabled={false}
                          onChange={(e) => patch(u.id, { role: e.target.value })}>
                    {["citizen", "authority", "admin"].map((r) => <option key={r}>{r}</option>)}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <select className="input !w-56 !py-1.5 text-xs"
                          value={u.department_id ?? ""}
                          onChange={(e) => patch(u.id, { department_id: e.target.value || null })}>
                    <option value="">{u.department_name ? "— clear —" : "— unassigned —"}</option>
                    {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => patch(u.id, { is_active: !u.is_active })}
                          className={`rounded-full px-3 py-1 text-[11px] font-bold ${
                            u.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"}`}>
                    {u.is_active ? "ACTIVE" : "DISABLED"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
