const STATUS_STYLES: Record<string, string> = {
  reported: "bg-slate-100 text-slate-700",
  clustered: "bg-slate-100 text-slate-700",
  action_required: "bg-amber-100 text-amber-800",
  assigned: "bg-blue-100 text-blue-800",
  in_progress: "bg-sky-100 text-sky-800",
  resolution_submitted: "bg-violet-100 text-violet-800",
  verification_pending: "bg-purple-100 text-purple-800",
  verified: "bg-emerald-100 text-emerald-800",
  resolved: "bg-emerald-100 text-emerald-800",
  reopened: "bg-orange-100 text-orange-800",
  closed: "bg-emerald-600/10 text-emerald-700",
  cancelled: "bg-slate-200 text-slate-500",
};

const LEVEL_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-700 ring-1 ring-red-200",
  high: "bg-orange-100 text-orange-700 ring-1 ring-orange-200",
  medium: "bg-amber-100 text-amber-800 ring-1 ring-amber-200",
  low: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
};

export function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function LevelBadge({ level }: { level?: string }) {
  if (!level) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
        LEVEL_STYLES[level] ?? LEVEL_STYLES.low
      }`}
    >
      {level}
    </span>
  );
}

export function SeverityDots({ value }: { value?: number | null }) {
  return (
    <span className="inline-flex items-center gap-0.5" title={`Severity ${value ?? "-"}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-3.5 rounded-full ${
            (value ?? 0) >= i
              ? i >= 4
                ? "bg-red-500"
                : i === 3
                  ? "bg-amber-400"
                  : "bg-emerald-400"
              : "bg-slate-200"
          }`}
        />
      ))}
    </span>
  );
}
