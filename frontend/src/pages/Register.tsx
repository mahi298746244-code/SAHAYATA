import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/CitizenLayout";

export default function Register() {
  const { register, login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", ward: "", password: "", confirm: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (form.password !== form.confirm) {
      setErr("Passwords do not match.");
      return;
    }
    if (form.password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register({
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || undefined as unknown as string,
        ward: form.ward || undefined as unknown as string,
        password: form.password,
      });
      await login(form.email.trim(), form.password);
      nav("/app", { replace: true });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "Registration failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-emerald-50 p-6">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 flex items-center gap-3">
          <Logo size={40} />
          <div>
            <div className="display text-xl font-bold">Join SAHAYATA</div>
            <div className="text-xs text-slate-500">Citizen accounts are free & always will be.</div>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Full name</label>
            <input className="input" required value={form.full_name} onChange={set("full_name")} placeholder="Aarti Kumari" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" required value={form.email} onChange={set("email")} placeholder="you@example.com" />
            </div>
            <div>
              <label className="label">Phone (optional)</label>
              <input className="input" value={form.phone} onChange={set("phone")} placeholder="+91…" />
            </div>
          </div>
          <div>
            <label className="label">Ward / area (optional)</label>
            <input className="input" value={form.ward} onChange={set("ward")} placeholder="Ward 4, Hindpiri" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" required value={form.password} onChange={set("password")} />
            </div>
            <div>
              <label className="label">Confirm</label>
              <input className="input" type="password" required value={form.confirm} onChange={set("confirm")} />
            </div>
          </div>

          {err && (
            <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">{err}</div>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already registered?{" "}
          <Link to="/login" className="font-semibold text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
