import React, { useState, useEffect } from "react";
import { ShieldCheck, ShieldOff, Copy, Check, RefreshCw, Database, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import api from "@/lib/glc";
import { PageHeader } from "@/components/common/GlcUI";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function Settings() {
  const { user } = useAuth();
  const [twoFA, setTwoFA] = useState({ enabled: false, loading: true });
  const [setup, setSetup] = useState(null);
  const [otp, setOtp] = useState("");
  const [copied, setCopied] = useState(false);
  const [sync, setSync] = useState(null);
  const [syncAll, setSyncAll] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const loadSync = () => {
    api.get("/sync/status").then((r) => setSync(r.data)).catch(() => {});
    api.get("/sync/all").then((r) => setSyncAll(r.data.synced)).catch(() => {});
  };
  useEffect(() => { loadSync(); }, []);

  const runSync = async (endpoint, label) => {
    setSyncing(true);
    try {
      const r = await api.post(endpoint);
      toast.success(`${label}: ${r.data.created} new, ${r.data.updated} updated`);
      loadSync();
    } catch { toast.error(`${label} sync failed`); }
    finally { setSyncing(false); }
  };

  useEffect(() => {
    api.get("/auth/me").then((r) => {
      setTwoFA({ enabled: !!r.data.twofa_enabled, loading: false });
    });
  }, []);

  const startSetup = async () => {
    const r = await api.get("/auth/2fa/setup");
    setSetup(r.data);
  };

  const enable2FA = async () => {
    try {
      await api.post("/auth/2fa/enable", { code: otp });
      toast.success("2FA enabled successfully!");
      setTwoFA({ enabled: true, loading: false });
      setSetup(null); setOtp("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invalid OTP");
    }
  };

  const disable2FA = async () => {
    const code = prompt("Enter your current 2FA code to disable:");
    if (!code) return;
    try {
      await api.post("/auth/2fa/disable", { code });
      toast.success("2FA disabled");
      setTwoFA({ enabled: false, loading: false });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invalid OTP");
    }
  };

  const copy = () => {
    navigator.clipboard.writeText(setup?.secret || "");
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="Settings" subtitle="Manage your account security and preferences" />

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <ShieldCheck size={20} className="text-[hsl(var(--primary))]" />
          <div>
            <div className="font-semibold text-[14px]">Two-Factor Authentication (2FA)</div>
            <div className="text-[12px] text-slate-500">Add an extra layer of security to your account</div>
          </div>
          <div className={`ml-auto text-[11px] px-2 py-1 rounded-full font-medium ${twoFA.enabled ? "bg-green-50 text-green-600" : "bg-slate-100 text-slate-500"}`}>
            {twoFA.enabled ? "Enabled" : "Disabled"}
          </div>
        </div>

        {!twoFA.enabled && !setup && (
          <button onClick={startSetup} className="px-4 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] font-medium hover:bg-[hsl(var(--primary))]/90">
            Enable 2FA
          </button>
        )}

        {setup && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <p className="text-[13px] text-slate-600">Scan this QR code with Google Authenticator or Authy:</p>
            <img src={setup.qr} alt="QR Code" className="w-48 h-48 border border-slate-200 rounded-xl p-2" />
            <div>
              <p className="text-[12px] text-slate-500 mb-1">Or enter this secret manually:</p>
              <div className="flex items-center gap-2">
                <code className="text-[12px] bg-slate-50 border border-slate-200 rounded px-3 py-1.5 font-mono">{setup.secret}</code>
                <button onClick={copy} className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">
                  {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} className="text-slate-400" />}
                </button>
              </div>
            </div>
            <div>
              <p className="text-[12px] text-slate-500 mb-1">Enter the 6-digit code from your app to verify:</p>
              <div className="flex gap-2">
                <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" className="w-36 h-10 rounded-lg border border-slate-200 text-center text-[18px] font-mono tracking-widest outline-none focus:border-[hsl(var(--primary))]" />
                <button onClick={enable2FA} disabled={otp.length !== 6} className="px-4 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] font-medium disabled:opacity-50">
                  Verify & Enable
                </button>
                <button onClick={() => { setSetup(null); setOtp(""); }} className="px-4 py-2 rounded-lg border border-slate-200 text-[13px] text-slate-500 hover:bg-slate-50">
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {twoFA.enabled && (
          <button onClick={disable2FA} className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-200 text-red-600 text-[13px] font-medium hover:bg-red-50">
            <ShieldOff size={14} /> Disable 2FA
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <Database size={20} className="text-[hsl(var(--primary))]" />
          <div>
            <div className="font-semibold text-[14px]">GlcZone Sync Status</div>
            <div className="text-[12px] text-slate-500">Live record counts — GlcZone.in vs CRM</div>
          </div>
          <button onClick={loadSync} className="ml-auto p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50" title="Refresh">
            <RefreshCw size={13} className="text-slate-400" />
          </button>
        </div>

        {sync && (
          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
              <div className="text-[11px] text-slate-500 font-medium uppercase tracking-wide mb-2">GlcZone.in (Source)</div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-[13px]"><span className="text-slate-600">Orders</span><span className="font-semibold">{sync.glczone?.orders ?? "—"}</span></div>
                <div className="flex justify-between text-[13px]"><span className="text-slate-600">Customers</span><span className="font-semibold">{sync.glczone?.customers ?? "—"}</span></div>
              </div>
            </div>
            <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
              <div className="text-[11px] text-slate-500 font-medium uppercase tracking-wide mb-2">CRM (Synced)</div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-[13px]"><span className="text-slate-600">Deals</span><span className="font-semibold">{sync.crm?.deals ?? "—"}</span></div>
                <div className="flex justify-between text-[13px]"><span className="text-slate-600">Customers</span><span className="font-semibold">{sync.crm?.customers ?? "—"}</span></div>
              </div>
            </div>
          </div>
        )}

        {syncAll && (
          <div className="mb-5">
            <div className="text-[11px] text-slate-500 font-medium uppercase tracking-wide mb-2">All Modules (synced records)</div>
            <div className="grid grid-cols-5 gap-2">
              {Object.entries(syncAll).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-slate-200 bg-white p-3 text-center">
                  <div className="text-[18px] font-bold text-slate-800">{v}</div>
                  <div className="text-[10px] text-slate-500 capitalize mt-0.5">{k}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {[
            { label: "Orders", endpoint: "/sync/orders-crm" },
            { label: "Products", endpoint: "/sync/products" },
            { label: "Customers", endpoint: "/sync/customers" },
            { label: "Deliveries", endpoint: "/sync/deliveries" },
            { label: "Pipeline Deals", endpoint: "/sync/deals" },
          ].map(({ label, endpoint }) => (
            <button key={label} onClick={() => runSync(endpoint, label)} disabled={syncing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-[12.5px] font-medium hover:bg-slate-50 disabled:opacity-50">
              <CheckCircle2 size={12} className="text-green-500" /> Sync {label}
            </button>
          ))}
        </div>
        {sync?.last_sync && <div className="text-[11px] text-slate-400 mt-3">Last refreshed: {new Date(sync.last_sync).toLocaleTimeString()}</div>}
      </div>
    </div>
  );
}
