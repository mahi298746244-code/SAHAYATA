import axios from "axios";

export const API = axios.create({ baseURL: "/api/v1" });

const ACCESS = "sahayata.access";
const REFRESH = "sahayata.refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

API.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`;
  return cfg;
});

let refreshing: Promise<void> | null = null;

API.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && tokens.refresh && !original._retried) {
      original._retried = true;
      try {
        refreshing ??= axios
          .post("/api/v1/auth/refresh", { refresh_token: tokens.refresh })
          .then(({ data }) => {
            tokens.set(data.access_token, data.refresh_token);
          })
          .finally(() => {
            refreshing = null;
          });
        await refreshing;
        return API(original);
      } catch {
        tokens.clear();
        window.location.href = "/login";
      }
    }
    throw error;
  },
);

export function mediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("http")) return url;
  return url.startsWith("/media") ? url : `/media-files/${url}`;
}
