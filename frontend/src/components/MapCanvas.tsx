import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MapPoint } from "../api/types";

const LEVEL_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#64748b",
};

function problemIcon(color: string, count: number) {
  const size = count >= 5 ? 40 : count >= 2 ? 34 : 28;
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:50% 50% 50% 4px;transform:rotate(45deg);background:${color};border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center">
      <span style="transform:rotate(-45deg);color:white;font-weight:800;font-size:${count >= 5 ? 14 : 11}px">${count > 1 ? count : ""}</span></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

const FACILITY_ICONS: Record<string, string> = {
  hospital: "🏥", school: "🏫", water: "🚰", emergency: "🚒",
};

export default function MapCanvas({
  points,
  center = [23.3441, 85.3096],
  zoom = 12,
  height = "70vh",
  onPick,
  pickLabel,
}: {
  points: MapPoint[];
  center?: [number, number];
  zoom?: number;
  height?: string;
  onPick?: (lat: number, lng: number) => void;
  pickLabel?: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { zoomControl: true }).setView(center, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    if (onPick) {
      map.current.on("click", (e: L.LeafletMouseEvent) => onPick(e.latlng.lat, e.latlng.lng));
    }
    setTimeout(() => map.current?.invalidateSize(), 150);
    return () => {
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const key = useMemo(() => JSON.stringify(points.map((p) => p.id)), [points]);

  useEffect(() => {
    const lg = layer.current;
    if (!lg || !map.current) return;
    lg.clearLayers();
    for (const p of points) {
      if (p.type === "problem") {
        L.marker([p.lat, p.lng], {
          icon: problemIcon(LEVEL_COLORS[p.priority_level ?? "low"] ?? LEVEL_COLORS.low, p.report_count ?? 1),
        })
          .bindPopup(
            `<b>${p.title}</b><br/>${p.category ?? ""} · ${p.report_count ?? 1} report(s)<br/><span style="text-transform:capitalize">${p.status ?? ""}</span>`,
          )
          .addTo(lg)
          .on("click", () => window.dispatchEvent(new CustomEvent("sahayata:point", { detail: p.id })));
      } else if (p.type === "facility") {
        L.marker([p.lat, p.lng], {
          icon: L.divIcon({
            className: "",
            html: `<div style="font-size:20px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))">${FACILITY_ICONS[p.facility_type ?? ""] ?? "📍"}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          }),
        }).bindPopup(`<b>${p.title}</b><br/>${p.facility_type}`).addTo(lg);
      } else if (p.type === "gap") {
        L.circleMarker([p.lat, p.lng], {
          radius: 10 + Math.min(20, (p.gap_score ?? 0) / 4),
          color: "#7c3aed",
          weight: 2,
          fillColor: "#a78bfa",
          fillOpacity: 0.35,
          dashArray: "4 3",
        })
          .bindPopup(
            `<b>Accessibility gap</b><br/>${p.title}<br/>${p.severity_label} · nearest facility ${p.nearest_distance_km != null ? `${p.nearest_distance_km.toFixed(1)} km` : "not found"}`,
          )
          .addTo(lg);
      } else {
        L.circleMarker([p.lat, p.lng], { radius: 6, color: "#4f46e5", fillOpacity: 0.85 })
          .bindPopup(`<b>${p.title}</b><br/>${p.status ?? ""}`)
          .addTo(lg);
      }
    }
  }, [key, points]);

  return (
    <div className="relative overflow-hidden rounded-2xl ring-1 ring-slate-200">
      <div ref={el} style={{ height }} />
      {onPick && pickLabel && (
        <div className="pointer-events-none absolute left-1/2 top-3 z-[500] -translate-x-1/2 rounded-full bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white shadow-lg">
          📍 {pickLabel}
        </div>
      )}
    </div>
  );
}
