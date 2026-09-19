import { useEffect, useState } from "react";
import { API } from "../../api/client";

interface SimResult {
  disclaimer: string;
  budget_input: number;
  problems_addressed: number;
  estimated_citizens_benefited: number;
  critical_problems_reduced: number;
  estimated_cost_used: number;
  remaining_budget: number;
  impact_score: number;
}

const SECTORS = [
  ["water", "💧 Water"],
  ["drainage", "🌊 Drainage"],
  ["garbage", "🗑️ Waste"],
  ["roads", "🛣️ Roads"],
  ["street_lighting", "💡 Lighting"],
  ["electricity", "⚡ Power"],
  ["healthcare", "🏥 Health"],
] as const;

export default function Simulator() {
  const [budget, setBudget] = useState(500000);
  const [sectors, setSectors] = useState<string[]>(["water", "drainage"]);
  const [result, setResult] = useState<SimResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run() {
    setBusy(true);
    try {
      const { data } = await API.post("/simulator/run", { budget, sectors });
      setResult(data);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-2xl font-bold">Impact simulator 🧪</h1>
        <p className="text-sm text-slate-500">
          Planning estimates for budget allocation — clearly labelled assumptions, never audited figures.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <div className="card space-y-5 p-6">
          <div>
            <label className="label">Budget: ₹{budget.toLocaleString()}</label>
            <input type="range" min={50000} max={5000000} step={50000} value={budget}
                   onChange={(e) => setBudget(Number(e.target.value))}
                   className="w-full accent-indigo-600" />
          </div>
          <div>
            <span className="label">Sectors in scope</span>
            <div className="flex flex-wrap gap-2">
              {SECTORS.map(([slug, label]) => (
                <button key={slug}
                        onClick={() => setSectors((s) =>
                          s.includes(slug) ? s.filter((x) => x !== slug) : [...s, slug])}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold ring-1 transition ${
                          sectors.includes(slug)
                            ? "bg-indigo-600 text-white ring-indigo-600"
                            : "bg-white text-slate-600 ring-slate-300"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button className="btn-primary w-full" disabled={busy || !sectors.length} onClick={run}>
            {busy ? "Simulating…" : "▶ Run simulation"}
          </button>
          <p className="rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-700 ring-1 ring-amber-200">
            ⚠️ Estimates use configurable per-problem cost/benefit assumptions stored by admins.
            They support planning discussions — they are not financial guarantees.
          </p>
        </div>

        <div className="space-y-4">
          {!result ? (
            <div className="card h-64 animate-pulse" />
          ) : (
            <>
              <div className="card flex items-center gap-6 p-6">
                <div className="relative h-28 w-28 shrink-0">
                  <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
                    <circle cx="18" cy="18" r="15.9" fill="none" stroke="#eef2f7" strokeWidth="4" />
                    <circle cx="18" cy="18" r="15.9" fill="none" stroke="#4f46e5" strokeWidth="4"
                            strokeLinecap="round" strokeDasharray={`${result.impact_score} ${100 - result.impact_score}`} />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center display text-xl font-extrabold">
                    {result.impact_score}
                  </div>
                </div>
                <div>
                  <h2 className="display text-lg font-bold">Impact score</h2>
                  <p className="text-sm text-slate-500">
                    Reaches <b>{result.estimated_citizens_benefited.toLocaleString()}</b> citizens and clears{" "}
                    <b>{result.critical_problems_reduced}</b> critical problem(s) within budget.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                {[
                  ["Problems addressed", result.problems_addressed],
                  ["Cost used", `₹${result.estimated_cost_used.toLocaleString()}`],
                  ["Remaining", `₹${result.remaining_budget.toLocaleString()}`],
                  ["Critical cleared", result.critical_problems_reduced],
                ].map(([k, v]) => (
                  <div key={String(k)} className="card p-4">
                    <div className="display text-xl font-extrabold text-slate-800">{v}</div>
                    <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{k}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
