import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/CitizenLayout";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const user = await login(email.trim(), password);
      nav(loc.state?.from ?? (user.role === "citizen" ? "/app" : "/console"), { replace: true });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setErr(msg ?? "Login failed – check your email and password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-indigo-700 via-indigo-600 to-emerald-600 lg:block">
        <div className="absolute inset-0 opacity-15" aria-hidden>
          <svg viewBox="0 0 500 500" className="h-full w-full" preserveAspectRatio="xMidYMid slice">
            <defs>
              <pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1.5" fill="white" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#g)" />
          </svg>
        </div>
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <Link to="/welcome" className="flex items-center gap-3">
            <Logo size={44} />
            <div>
              <div className="display text-2xl font-bold">SAHAYATA</div>
              <div className="text-xs uppercase tracking-[0.25em] text-indigo-100">
                Smart Citizen Support
              </div>
            </div>
          </Link>

          <div className="max-w-md">
            <h1 className="display text-4xl font-extrabold leading-tight">
              Your city, one report at a time.
            </h1>
            <p className="mt-4 text-indigo-100">
              Report civic issues in seconds — photo, video or just your voice. AI routes them,
              departments act, <b>you verify</b> the fix.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-indigo-50">
              {[
                ["📍", "Pin the exact spot on the map"],
                ["🤖", "AI classifies & prioritises automatically"],
                ["✅", "Transparent verification of every resolution"],
              ].map(([i, t]) => (
                <li key={t} className="flex items-center gap-3 rounded-xl bg-white/10 px-4 py-3 backdrop-blur-sm">
                  <span className="text-lg">{i}</span> {t}
                </li>
              ))}
            </ul>
          </div>

          <div className="text-xs text-indigo-200">
            Built for citizens · Powered by transparent AI · Made in Jharkhand 🇮🇳
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Logo size={36} />
            <span className="display text-xl font-bold">SAHAYATA</span>
          </div>
          <h2 className="display text-3xl font-bold">Welcome back</h2>
          <p className="mt-1 text-sm text-slate-500">Sign in to report issues and track progress.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" required value={email}
                     onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" required value={password}
                     onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {err && (
              <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
                {err}
              </div>
            )}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-sm text-slate-500">
            New here?{" "}
            <Link to="/register" className="font-semibold text-indigo-600 hover:underline">
              Create a citizen account
            </Link>
          </p>

          <details className="mt-6 rounded-xl bg-slate-50 p-4 text-xs text-slate-500 ring-1 ring-slate-200">
            <summary className="cursor-pointer font-semibold text-slate-600">Demo accounts</summary>
            <div className="mt-2 space-y-1 font-mono">
              <div>citizen → aarti.demo@sahayata.in / demo12345</div>
              <div>officer → officer.demo@sahayata.in / demo12345</div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
