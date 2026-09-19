import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "../api/client";
import type { MapPoint } from "../api/types";
import MapCanvas from "../components/MapCanvas";

const BBOX = { sw_lat: 23.1, sw_lng: 85.05, ne_lat: 23.6, ne_lng: 85.6 };

export default function MapPage({ staff = false }: { staff?: boolean }) {
  const nav = useNavigate();
  const [problems, setProblems] = useState<MapPoint[]>([]);
  const [facilities, setFacilities] = useState<MapPoint[]>([]);
  const [gaps, setGaps] = useState<MapPoint[]>([]);
  const [layers, setLayers] = useState({ problems: true, facilities: true, gaps: false });

  useEffect(() => {
    API.get("/map/problems", { params: BBOX }).then((r) => setProblems(r.data));
    API.get("/map/facilities", { params: BBOX }).then((r) => setFacilities(r.data));
    API.get("/map/gaps").then((r) => setGaps(r.data)).catch(() => setGaps([]));
  }, []);

  const points = [
    ...(layers.problems ? problems : []),
    ...(layers.facilities ? facilities : []),
    ...(layers.gaps ? gaps : []),
  ];

  useEffect(() => {
    function onPoint(e: Event) {
      const code = (e as CustomEvent<string>).detail;
      if (typeof code === "string" && code.startsWith("PRB-")) {
        nav(staff ? `/console/problems/${code}` : `/app/problems/${code}`);
      }
    }
    window.addEventListener("sahayata:point", onPoint);
    return () => window.removeEventListener("sahayata:point", onPoint);
  }, [nav, staff]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="display text-2xl font-bold">City map</h1>
        <p className="text-sm text-slate-500">
          Pins show merged problem clusters — bigger & redder means more urgent. Tap a pin for details.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {([
          ["problems", "🎯 Problem clusters", "bg-indigo-600"],
          ["facilities", "🏥 Public facilities", "bg-emerald-600"],
          ["gaps", "🕸️ Accessibility gaps", "bg-violet-600"],
        ] as const).map(([key, label, active]) => (
          <button key={key}
                  onClick={() => setLayers((l) => ({ ...l, [key]: !l[key as keyof typeof l] }))}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ring-1 transition ${
                    layers[key as keyof typeof layers]
                      ? `${active} text-white ring-transparent`
                      : "bg-white text-slate-500 ring-slate-300"
                  }`}>
            {label}
          </button>
        ))}
      </div>

      <MapCanvas points={points} height="72vh" zoom={12} />

      <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <Legend color="#dc2626" label="Critical priority" />
        <Legend color="#f97316" label="High priority" />
        <Legend color="#f59e0b" label="Medium priority" />
        <Legend color="#64748b" label="Low / normal" />
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="card flex items-center gap-2 px-3 py-2">
      <span className="h-3 w-3 rounded-full" style={{ background: color }} />
      <span className="font-medium text-slate-600">{label}</span>
    </div>
  );
}
