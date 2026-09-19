import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API, tokens } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: Record<string, string>) => Promise<User>;
  logout: () => void;
}

const Ctx = createContext<AuthState>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false);
      return;
    }
    API.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await API.post("/auth/login-json", { email, password });
    tokens.set(data.access_token, data.refresh_token);
    const me = await API.get("/auth/me");
    setUser(me.data);
    return me.data as User;
  }, []);

  const register = useCallback(async (payload: Record<string, string>) => {
    const { data } = await API.post("/auth/register", payload);
    return data as User;
  }, []);

  const logout = useCallback(() => {
    const refresh = tokens.refresh;
    if (refresh) API.post("/auth/logout", { refresh_token: refresh }).catch(() => {});
    tokens.clear();
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}
