import { useEffect, useState } from "react";
import { API, mediaUrl } from "../api/client";
import type { MediaItem as ApiMedia } from "../api/types";

interface Item {
  id: string;
  kind: string;
}

function AuthedMedia({ item }: { item: Item }) {
  const [src, setSrc] = useState<string>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let url: string | undefined;
    API.get(`/media/${item.id}`, { responseType: "blob" })
      .then((r) => {
        url = URL.createObjectURL(r.data);
        setSrc(url);
      })
      .catch(() => setFailed(true));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [item.id]);

  if (failed)
    return (
      <div className="flex h-full min-h-24 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
        media unavailable
      </div>
    );
  if (!src)
    return <div className="h-full min-h-24 animate-pulse rounded-xl bg-slate-200" />;

  if (item.kind === "video")
    return <video src={src} controls className="w-full rounded-xl bg-black" preload="metadata" />;
  if (item.kind === "audio")
    return <audio src={src} controls className="w-full" />;
  return <img src={src} alt="" loading="lazy" className="w-full rounded-xl object-cover" />;
}

export default function MediaGallery({ media }: { media: (ApiMedia & Record<string, unknown>)[] }) {
  if (!media?.length) return null;
  void mediaUrl; // kept for absolute-url support
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {media.map((m) => (
        <AuthedMedia key={m.id} item={{ id: m.id, kind: m.kind }} />
      ))}
    </div>
  );
}
