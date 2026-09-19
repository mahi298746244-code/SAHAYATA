import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "../../api/client";
import MapCanvas from "../../components/MapCanvas";
import type { MapPoint } from "../../api/types";

interface Category {
  id: string;
  name: string;
  slug: string;
  icon?: string;
}

export default function NewReport() {
  const nav = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [landmark, setLandmark] = useState("");
  const [ward, setWard] = useState("");
  const [latlng, setLatlng] = useState<[number, number] | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [listening, setListening] = useState(false);
  const [recordingAudio, setRecordingAudio] = useState(false);
  const [gpsBusy, setGpsBusy] = useState(false);
  const speechRef = useRef<{ stop(): void } | null>(null);
  const audioRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    API.get("/catalog/categories").then((r) => {
      setCategories(r.data);
      if (r.data.length) setCategoryId(r.data[0].id);
    });
  }, []);

  function pick(lat: number, lng: number) {
    setLatlng([+lat.toFixed(6), +lng.toFixed(6)]);
  }

  function useGps() {
    if (!navigator.geolocation) {
      setErr("GPS not available — tap the map instead.");
      return;
    }
    setGpsBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => pick(pos.coords.latitude, pos.coords.longitude),
      () => setErr("Couldn't get GPS — tap your spot on the map instead."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
    setTimeout(() => setGpsBusy(false), 800);
  }

  /* Voice input (Web Speech API – Chrome/Edge; graceful fallback elsewhere) */
  function toggleVoice() {
    interface SpeechRecognitionLike {
      lang: string;
      continuous: boolean;
      interimResults: boolean;
      start(): void;
      stop(): void;
      onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
      onend: (() => void) | null;
    }
    const SR =
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike }).webkitSpeechRecognition;
    if (!SR) {
      setErr("Voice input isn't supported in this browser — you can also record audio instead.");
      return;
    }
    if (listening) {
      speechRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = "en-IN";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript + " ";
      setDescription(text.trim());
    };
    rec.onend = () => setListening(false);
    rec.start();
    speechRef.current = rec;
    setListening(true);
  }

  /* Audio note recording */
  async function toggleAudio() {
    if (audioRef.current && audioRef.current.state === "recording") {
      audioRef.current.stop();
      setRecordingAudio(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
        const f = new File([blob], `voice-note-${Date.now()}.webm`, { type: blob.type });
        setFiles((fs) => [...fs, f]);
        stream.getTracks().forEach((t) => t.stop());
        setRecordingAudio(false);
      };
      mr.start();
      chunksRef.current = [];
      audioRef.current = mr;
      setRecordingAudio(true);
    } catch {
      setErr("Microphone permission denied.");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!latlng) {
      setErr("Please choose the location — use GPS or tap the map.");
      return;
    }
    setBusy(true);
    try {
      // stop any active recorder before upload
      if (audioRef.current && audioRef.current.state === "recording") audioRef.current.stop();
      const fd = new FormData();
      fd.set("title", title);
      fd.set("description", description);
      fd.set("latitude", String(latlng[0]));
      fd.set("longitude", String(latlng[1]));
      fd.set("category_id", categoryId);
      fd.set("landmark", landmark);
      fd.set("ward", ward);
      fd.set("location_source", "map");
      files.slice(0, 6).forEach((f) => {
        if (f.type.startsWith("video")) fd.append("videos", f);
        else if (f.type.startsWith("audio")) fd.append("audios", f);
        else fd.append("images", f);
      });
      const { data } = await API.post("/reports", fd);
      nav(`/app/problems/${data.cluster_code ?? ""}`, { state: { created: data.code } });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "Could not submit report. Check the fields.");
    } finally {
      setBusy(false);
    }
  }

  const points: MapPoint[] = latlng
    ? [{ id: "pick", type: "report", lat: latlng[0], lng: latlng[1], title: "Selected location" }]
    : [];

  return (
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-5">
        <div>
          <h1 className="display text-2xl font-bold">Report an issue</h1>
          <p className="mt-1 text-sm text-slate-500">
            The more precise the location, the faster the fix.
          </p>
        </div>

        {/* Location */}
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="label !mb-0">1 · Where is it?</span>
            <button type="button" onClick={useGps} className="btn-ghost !py-1.5 text-indigo-600">
              {gpsBusy ? "…" : "📡 Use my GPS"}
            </button>
          </div>
          <MapCanvas
            points={points}
            height="260px"
            zoom={13}
            onPick={pick}
            pickLabel="Tap the exact spot"
          />
          {latlng && (
            <div className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700 ring-1 ring-emerald-200">
              📍 Pinned at {latlng[0]}, {latlng[1]}
            </div>
          )}
        </div>

        {/* Category */}
        <div className="card p-4">
          <span className="label">2 · What kind of problem?</span>
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setCategoryId(c.id)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ring-1 transition ${
                  categoryId === c.id
                    ? "bg-indigo-600 text-white ring-indigo-600"
                    : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Not sure? Skip it — AI will classify from your description & photo.
          </p>
        </div>

        {/* Details */}
        <div className="card space-y-4 p-4">
          <span className="label">3 · Describe it</span>
          <input className="input" required maxLength={200} placeholder="Short title, e.g. 'Open pothole near school gate'"
                 value={title} onChange={(e) => setTitle(e.target.value)} />
          <div>
            <div className="mb-1 flex items-center justify-between">
              <textarea className="input min-h-24" placeholder="Details (optional)…"
                        value={description} onChange={(e) => setDescription(e.target.value)} />
              <button type="button" onClick={toggleVoice}
                      className={`ml-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-1 transition ${
                        listening ? "animate-pulse bg-red-500 text-white ring-red-500" : "bg-white text-slate-500 ring-slate-300 hover:bg-slate-50"
                      }`}
                      title="Speak instead of typing">
                🎙️
              </button>
            </div>
            {listening && <p className="text-xs font-semibold text-red-500">Listening… speak now</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input className="input" placeholder="Landmark (optional)" value={landmark}
                   onChange={(e) => setLandmark(e.target.value)} />
            <input className="input" placeholder="Ward (optional)" value={ward}
                   onChange={(e) => setWard(e.target.value)} />
          </div>
        </div>

        {/* Media */}
        <div className="card p-4">
          <span className="label">4 · Add proof (photo / video / voice note)</span>
          <div className="grid grid-cols-3 gap-2">
            {[
              { accept: "image/*", capture: "environment", icon: "📷", label: "Photo" },
              { accept: "video/*", capture: "environment", icon: "🎥", label: "Video" },
            ].map((b) => (
              <label key={b.label}
                     className="flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed border-slate-300 py-4 text-xs font-semibold text-slate-500 hover:border-indigo-400 hover:text-indigo-600">
                <span className="text-xl">{b.icon}</span> {b.label}
                <input type="file" hidden accept={b.accept} capture={b.capture as "environment"}
                       multiple={b.label === "Photo"}
                       onChange={(e) =>
                         setFiles((fs) => [...fs, ...Array.from(e.target.files ?? [])].slice(0, 6))
                       } />
              </label>
            ))}
            <button type="button" onClick={toggleAudio}
                    className="flex flex-col items-center gap-1 rounded-xl border border-dashed border-slate-300 py-4 text-xs font-semibold text-slate-500 hover:border-indigo-400 hover:text-indigo-600">
              <span className="text-xl">{recordingAudio ? "⏹️" : "🎤"}</span>
              {recordingAudio ? "Stop" : "Voice note"}
            </button>
          </div>
          {files.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
              {files.map((f, i) => (
                <li key={i} className="rounded-full bg-slate-100 px-2.5 py-1">
                  {f.type.startsWith("video") ? "🎥" : f.type.startsWith("audio") ? "🎤" : "📷"}{" "}
                  {f.name.slice(0, 18)}
                  <button type="button" className="ml-1 text-slate-400 hover:text-red-500"
                          onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}>✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {err && (
          <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">{err}</div>
        )}
        <button className="btn-primary w-full py-3 text-base" disabled={busy}>
          {busy ? "Submitting…" : "🚀 Submit report"}
        </button>
      </div>

      {/* Live preview */}
      <div className="hidden lg:block">
        <div className="sticky top-24 card overflow-hidden">
          <div className="bg-gradient-to-br from-indigo-600 to-emerald-500 px-6 py-8 text-white">
            <div className="text-xs font-bold uppercase tracking-widest opacity-70">Live preview</div>
            <h3 className="display mt-2 text-xl font-bold">{title || "Your issue title"}</h3>
            <p className="mt-1 line-clamp-3 text-sm text-indigo-100">
              {description || "Your description will appear here."}
            </p>
          </div>
          <div className="space-y-3 p-6 text-sm">
            <Row k="Category" v={categories.find((c) => c.id === categoryId)?.name ?? "AI will decide"} />
            <Row k="Location" v={latlng ? `${latlng[0]}, ${latlng[1]}` : "not chosen yet"} />
            <Row k="Attachments" v={`${files.length} file(s)`} />
            <Row k="After submit" v="AI classifies → clustered with duplicates → priority scored → department assigned" />
          </div>
        </div>
      </div>
    </form>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2 last:border-0">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{k}</span>
      <span className="text-right text-sm text-slate-700">{v}</span>
    </div>
  );
}
