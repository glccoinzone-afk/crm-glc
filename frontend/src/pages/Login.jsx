import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, Loader2, IdCard, KeyRound, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import api from "@/lib/glc";

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [employeeCode, setEmployeeCode] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [twoFAMode, setTwoFAMode] = useState(false);
  const [tempToken, setTempToken] = useState("");
  const [otp, setOtp] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await login(employeeCode.trim(), pin.trim());
      if (res?.requires_2fa) {
        setTempToken(res.temp_token);
        setTwoFAMode(true);
        toast.info("Enter your 2FA code to continue");
      } else {
        toast.success("Welcome back to GLC Zone");
        nav("/");
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Invalid Employee ID or PIN");
    } finally {
      setLoading(false);
    }
  };

  const verify2FA = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post("/auth/2fa/verify", { temp_token: tempToken, code: otp });
      localStorage.setItem("glc_token", r.data.token);
      localStorage.setItem("glc_user", JSON.stringify(r.data.user));
      window.location.href = "/crm";
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Invalid OTP code");
    } finally {
      setLoading(false);
    }
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

          {!twoFAMode ? (
            <>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Sign in to your workspace</h2>
              <p className="text-[13.5px] text-slate-500 mt-1.5">Enter your Employee ID and PIN to continue.</p>
              <form onSubmit={submit} className="mt-8 space-y-4">
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Employee ID</label>
                  <div className="mt-1.5 relative">
                    <IdCard size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input data-testid="login-employee-id" value={employeeCode} onChange={(e) => setEmployeeCode(e.target.value.toUpperCase())} type="text" placeholder="EMP-XXXXX" className="w-full h-11 pl-10 pr-3 rounded-xl border border-slate-200 focus:border-[hsl(var(--primary))] outline-none text-[14px] font-mono tracking-wide" autoComplete="off" />
                  </div>
                </div>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">4-Digit PIN</label>
                  <div className="mt-1.5 relative">
                    <KeyRound size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input data-testid="login-pin" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))} type="password" inputMode="numeric" maxLength={4} placeholder="••••" className="w-full h-11 pl-10 pr-3 rounded-xl border border-slate-200 focus:border-[hsl(var(--primary))] outline-none text-[16px] font-mono tracking-[0.4em]" autoComplete="off" />
                  </div>
                </div>
                <button data-testid="login-submit" disabled={loading || employeeCode.length < 3 || pin.length !== 4} className="w-full h-11 rounded-xl bg-[hsl(var(--primary))] text-white text-[14px] font-medium hover:bg-[hsl(var(--primary))]/90 disabled:opacity-50 active:scale-[0.99] transition-transform grid place-items-center">
                  {loading ? <Loader2 className="animate-spin" size={16} /> : "Sign in"}
                </button>
              </form>
              <p className="mt-6 text-[12px] text-slate-400 text-center">Don't have an Employee ID? Contact your Super Admin.</p>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 rounded-xl bg-[hsl(var(--primary))]/10 grid place-items-center">
                  <ShieldCheck size={22} className="text-[hsl(var(--primary))]" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-slate-900">Two-Factor Authentication</h2>
                  <p className="text-[13px] text-slate-500">Enter the 6-digit code from your authenticator app</p>
                </div>
              </div>
              <form onSubmit={verify2FA} className="space-y-4">
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">OTP Code</label>
                  <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} type="text" inputMode="numeric" maxLength={6} placeholder="000000" className="mt-1.5 w-full h-14 rounded-xl border border-slate-200 focus:border-[hsl(var(--primary))] outline-none text-[28px] font-mono tracking-[0.5em] text-center" autoFocus />
                </div>
                <button disabled={loading || otp.length !== 6} className="w-full h-11 rounded-xl bg-[hsl(var(--primary))] text-white text-[14px] font-medium hover:bg-[hsl(var(--primary))]/90 disabled:opacity-50 grid place-items-center">
                  {loading ? <Loader2 className="animate-spin" size={16} /> : "Verify & Sign in"}
                </button>
                <button type="button" onClick={() => { setTwoFAMode(false); setOtp(""); }} className="w-full text-[13px] text-slate-400 hover:text-slate-600">← Back to login</button>
              </form>
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
