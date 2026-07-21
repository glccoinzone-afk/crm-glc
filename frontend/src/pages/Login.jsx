import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, Loader2, Mail, Lock } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("bishwajeet@glczone.in");
  const [password, setPassword] = useState("Admin@123");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back to GLC Zone");
      nav("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const quickPick = (e) => {
    setEmail(e);
    setPassword("Admin@123");
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left brand panel */}
      <div className="hidden lg:flex relative bg-[hsl(var(--primary))] text-white p-12 flex-col justify-between overflow-hidden">
        <div className="absolute inset-0 opacity-[0.07] bg-grid" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/10 grid place-items-center">
              <Sparkles size={20} />
            </div>
            <div className="text-lg font-semibold tracking-tight">GLC Zone</div>
          </div>
        </div>
        <div className="relative">
          <h1 className="text-[40px] leading-[1.05] font-semibold tracking-tight max-w-lg">
            Run every vertical<br /> from a single, sharp platform.
          </h1>
          <p className="text-white/70 mt-4 max-w-md text-[14.5px] leading-relaxed">
            CRM, sales, inventory, purchase, delivery, HR, accounting, projects — engineered for India-first GST compliance and built for scale from 5 to 500 users.
          </p>
          <div className="mt-8 grid grid-cols-4 gap-2 max-w-md">
            {["GLC Fresh", "GLC Store", "GLC Garden", "GLC Hardwares", "Dhani Jewellers", "India Mandi", "GLC Property", "GLC Legal"].map((v) => (
              <div key={v} className="text-[10.5px] font-medium bg-white/10 border border-white/10 rounded-lg px-2 py-1.5 text-center">{v}</div>
            ))}
          </div>
        </div>
        <div className="relative text-[12px] text-white/60">© {new Date().getFullYear()} GLC Zone Private Limited</div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-8 md:p-12 bg-white">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
          <div className="lg:hidden mb-8 flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-[hsl(var(--primary))] text-white grid place-items-center">
              <Sparkles size={18} />
            </div>
            <div className="text-lg font-semibold">GLC Zone</div>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Sign in to your workspace</h2>
          <p className="text-[13.5px] text-slate-500 mt-1.5">Enter your GLC Zone credentials to continue.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Email</label>
              <div className="mt-1.5 relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  data-testid="login-email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  type="email"
                  className="w-full h-11 pl-10 pr-3 rounded-xl border border-slate-200 focus:border-[hsl(var(--primary))] outline-none text-[14px]"
                />
              </div>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Password</label>
              <div className="mt-1.5 relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  data-testid="login-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  className="w-full h-11 pl-10 pr-3 rounded-xl border border-slate-200 focus:border-[hsl(var(--primary))] outline-none text-[14px]"
                />
              </div>
            </div>
            <button
              data-testid="login-submit"
              disabled={loading}
              className="w-full h-11 rounded-xl bg-[hsl(var(--primary))] text-white text-[14px] font-medium hover:bg-[hsl(var(--primary))]/90 disabled:opacity-70 active:scale-[0.99] transition-transform grid place-items-center"
            >
              {loading ? <Loader2 className="animate-spin" size={16} /> : "Sign in"}
            </button>
          </form>

          <div className="mt-8">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">Quick sign-in (demo)</div>
            <div className="grid grid-cols-2 gap-2">
              {[
                { name: "Super Admin", email: "bishwajeet@glczone.in" },
                { name: "Admin", email: "riddhi@glczone.in" },
                { name: "Manager", email: "dev@glczone.in" },
                { name: "Support Exec", email: "danish@glczone.in" },
              ].map((p) => (
                <button
                  key={p.email}
                  type="button"
                  data-testid={`quick-login-${p.name.toLowerCase().replace(/\s+/g, "-")}`}
                  onClick={() => quickPick(p.email)}
                  className="text-left px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-[12px]"
                >
                  <div className="font-medium text-slate-800">{p.name}</div>
                  <div className="text-slate-500 truncate">{p.email}</div>
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
