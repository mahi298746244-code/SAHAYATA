import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "../api/client";

interface Notif {
  id: string;
  type: string;
  title: string;
  body: string;
  data: { problem_code?: string } | null;
  read_at: string | null;
  created_at: string;
}

const ICONS: Record<string, string> = {
  welcome: "👋",
  status_changed: "🔧",
  verification_requested: "✅",
  verification_passed: "🎉",
  verification_failed: "⚠️",
};

export default function NotificationBell({ basePath = "/app" }: { basePath?: string }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);
  const nav = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    API.get("/notifications", { params: { page_size: 15 } })
      .then((r) => {
        setItems(r.data.items);
        setUnread(r.data.unread);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function openItem(n: Notif) {
    if (!n.read_at) API.post(`/notifications/${n.id}/read`).then(load).catch(() => {});
    setOpen(false);
    const code = n.data?.problem_code;
    if (code) nav(`${basePath}/problems/${code}`);
  }

  return (
    <div className="relative" ref={boxRef}>
      <button onClick={() => setOpen((o) => !o)}
              className="relative flex h-9 w-9 items-center justify-center rounded-full text-lg ring-1 ring-slate-200 transition hover:bg-slate-50"
              aria-label="Notifications">
        🔔
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 max-h-96 w-80 overflow-y-auto rounded-xl border border-slate-100 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-400">Notifications</span>
            {unread > 0 && (
              <button onClick={() => API.post("/notifications/read-all").then(load).catch(() => {})}
                      className="text-[11px] font-semibold text-indigo-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">Nothing yet — you're all caught up.</div>
          ) : (
            items.map((n) => (
              <button key={n.id} onClick={() => openItem(n)}
                      className={`flex w-full gap-2.5 px-3 py-2.5 text-left transition hover:bg-indigo-50/60 ${n.read_at ? "" : "bg-indigo-50/30"}`}>
                <span className="mt-0.5 shrink-0">{ICONS[n.type] ?? "🔔"}</span>
                <span className="min-w-0">
                  <span className={`block truncate text-xs ${n.read_at ? "font-medium text-slate-600" : "font-bold text-slate-800"}`}>
                    {n.title}
                  </span>
                  <span className="line-clamp-2 block text-[11px] leading-snug text-slate-500">{n.body}</span>
                  <span className="block pt-0.5 text-[10px] text-slate-400">
                    {new Date(n.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </span>
                {!n.read_at && <span className="ml-auto mt-1 h-2 w-2 shrink-0 rounded-full bg-indigo-500" />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
