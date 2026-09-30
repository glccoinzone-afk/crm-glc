import React, { useEffect, useState } from "react";
import { Check, X, Banknote, RotateCcw, ChevronDown } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { toast } from "sonner";

export default function SellerManagement() {
  const [tab, setTab] = useState("withdrawals");
  const [withdrawals, setWithdrawals] = useState([]);
  const [returns, setReturns] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [w, r] = await Promise.all([
        api.get("/withdrawals"),
        api.get("/returns"),
      ]);
      setWithdrawals(w.data.items || []);
      setReturns(r.data.items || []);
    } catch(e) { toast.error("Load failed"); }
    setLoading(false);
  };
  useEffect(() => { loadAll(); }, []);

  const wAction = async (id, action) => {
    await api.post(`/withdrawals/${id}/${action}`);
    toast.success(`${action.replace("-"," ")} done`);
    loadAll();
  };
  const rAction = async (id, action) => {
    await api.post(`/returns/${id}/${action}`);
    toast.success(`Return ${action}d`);
    loadAll();
  };

  const wCols = [
    { key: "sellerName", header: "Seller" },
    { key: "amount", header: "Amount", mono: true, align: "right", render: (r) => fmtInr(r.amount || 0) },
    { key: "method", header: "Method" },
    { key: "upiId", header: "UPI/Account", render: (r) => r.upiId || r.bankAccount || "—" },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "actions", header: "", align: "right", render: (r) => (
      r.status === "PENDING" ? (
        <div className="flex items-center gap-1 justify-end">
          <button onClick={() => wAction(r.id, "approve")} className="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-600 border border-emerald-200" title="Approve"><Check size={13} /></button>
          <button onClick={() => wAction(r.id, "reject")} className="p-1.5 rounded-md hover:bg-rose-50 text-rose-600 border border-rose-200" title="Reject"><X size={13} /></button>
        </div>
      ) : r.status === "APPROVED" ? (
        <button onClick={() => wAction(r.id, "mark-paid")} className="text-[11.5px] px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">Mark Paid</button>
      ) : <span className="text-[11px] text-slate-400">—</span>
    )},
  ];

  const rCols = [
    { key: "orderNo", header: "Order" },
    { key: "customerName", header: "Customer" },
    { key: "reason", header: "Reason" },
    { key: "amount", header: "Refund", mono: true, align: "right", render: (r) => fmtInr(r.amount || 0) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "actions", header: "", align: "right", render: (r) => (
      r.status === "PENDING" ? (
        <div className="flex items-center gap-1 justify-end">
          <button onClick={() => rAction(r.id, "approve")} className="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-600 border border-emerald-200" title="Approve"><Check size={13} /></button>
          <button onClick={() => rAction(r.id, "reject")} className="p-1.5 rounded-md hover:bg-rose-50 text-rose-600 border border-rose-200" title="Reject"><X size={13} /></button>
        </div>
      ) : <span className="text-[11px] text-slate-400">—</span>
    )},
  ];

  const pendingW = withdrawals.filter(w => w.status === "PENDING").length;
  const pendingR = returns.filter(r => r.status === "PENDING").length;

  return (
    <div className="space-y-6">
      <PageHeader testId="seller-page" title="Seller Management" subtitle="Manage seller withdrawals and customer return requests" />

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Withdrawals", value: withdrawals.length, icon: Banknote, color: "text-blue-600" },
          { label: "Pending Withdrawals", value: pendingW, icon: Banknote, color: "text-amber-600" },
          { label: "Total Returns", value: returns.length, icon: RotateCcw, color: "text-purple-600" },
          { label: "Pending Returns", value: pendingR, icon: RotateCcw, color: "text-rose-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11.5px] text-slate-500">{label}</div>
              <Icon size={16} className={color} />
            </div>
            <div className="text-[24px] font-bold text-slate-900">{value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        {[
          { key: "withdrawals", label: `Withdrawals${pendingW ? ` (${pendingW} pending)` : ""}` },
          { key: "returns", label: `Returns${pendingR ? ` (${pendingR} pending)` : ""}` },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-lg text-[12.5px] font-medium transition-all ${tab === t.key ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "withdrawals" && (
        withdrawals.length === 0
          ? <EmptyState icon={Banknote} title="No withdrawal requests" description="Seller withdrawal requests will appear here." />
          : <DataGrid columns={wCols} rows={withdrawals} loading={loading} testId="withdrawals-grid" />
      )}
      {tab === "returns" && (
        returns.length === 0
          ? <EmptyState icon={RotateCcw} title="No return requests" description="Customer return requests will appear here." />
          : <DataGrid columns={rCols} rows={returns} loading={loading} testId="returns-grid" />
      )}
    </div>
  );
}
