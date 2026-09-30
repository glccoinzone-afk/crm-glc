import React, { useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader } from "@/components/common/GlcUI";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";

const STAGES = [
  { key: "NEW", label: "New", color: "#0EA5E9" },
  { key: "CONTACTED", label: "Contacted", color: "#6366F1" },
  { key: "QUALIFIED", label: "Qualified", color: "#8B5CF6" },
  { key: "PROPOSAL", label: "Proposal", color: "#F59E0B" },
  { key: "NEGOTIATION", label: "Negotiation", color: "#EA580C" },
  { key: "WON", label: "Won", color: "#10B981" },
];

export default function Pipeline() {
  const [deals, setDeals] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", customerName: "", customerPhone: "", customerEmail: "", value: 0, probability: 40, stage: "NEW", expectedClose: "", notes: "" });
  const [dragged, setDragged] = useState(null);
  const [customers, setCustomers] = useState([]);
  useEffect(() => {
    api.get("/customers", { params: { limit: 100 } }).then((r) => setCustomers(r.data.items || []));
  }, []);
  const fillCustomer = (cid) => {
    const c = customers.find((x) => x.id === cid);
    if (c) setForm((f) => ({ ...f, customerName: c.name, customerPhone: c.phone||"", customerEmail: c.email||"" }));
  };

  const [syncing, setSyncing] = useState(false);
  const [canSync, setCanSync] = useState(false);
  useEffect(() => {
    api.get("/rbac/me").then((r) => {
      const perms = r.data.modules || [];
      setCanSync(perms.includes("*") || perms.some((p) => ["sales", "crm", "sales.orders"].includes(p)));
    });
  }, []);
  const load = () => api.get("/deals").then((r) => setDeals(r.data.items || []));
  const syncGlczone = async () => {
    setSyncing(true);
    try {
      const r1 = await api.post("/sync/orders");
      const r2 = await api.post("/sync/customers");
      toast.success(`Synced ${r1.data.created} new orders, ${r2.data.created} new customers`);
      load();
    } catch { toast.error("Sync failed"); }
    finally { setSyncing(false); }
  };
  useEffect(() => { load(); }, []);

  const byStage = (k) => deals.filter((d) => d.stage === k);
  const totalStage = (k) => byStage(k).reduce((s, d) => s + (d.value || 0), 0);

  const move = async (d, stage) => {
    if (d.stage === stage) return;
    await api.put(`/deals/${d.id}`, { stage });
    setDeals((prev) => prev.map((x) => (x.id === d.id ? { ...x, stage } : x)));
    toast.success(`Moved to ${stage}`);
  };

  const save = async () => {
    await api.post("/deals", form);
    toast.success("Deal added");
    setOpen(false);
    setForm({ title: "", customerName: "", value: 0, probability: 40, stage: "NEW" });
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          testId="pipeline-page"
          title="Sales Pipeline"
          subtitle="Drag deals across stages to move them through your funnel"
          actions={
            <button data-testid="new-deal-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
              <Plus size={14} /> Add Deal
            </button>
          }
        />
        {canSync && (
          <button onClick={syncGlczone} disabled={syncing} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 text-[12.5px] font-medium hover:bg-slate-50 disabled:opacity-50">
            <RefreshCw size={13} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Syncing…" : "Sync glczone.in"}
          </button>
        )}
      </div>

      <div className="flex gap-4 overflow-x-auto pb-2" data-testid="pipeline-board">
        {STAGES.map((st) => (
          <div
            key={st.key}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => dragged && move(dragged, st.key)}
            className="kanban-col min-w-[280px] w-[280px] p-3 flex flex-col"
          >
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: st.color }} />
                <div className="text-[13px] font-semibold text-slate-800">{st.label}</div>
                <span className="text-[11px] font-mono text-slate-500 bg-white px-1.5 py-0.5 rounded">{byStage(st.key).length}</span>
              </div>
              <div className="text-[11px] font-mono tabular text-slate-600">{fmtInr(totalStage(st.key))}</div>
            </div>
            <div className="space-y-2">
              {byStage(st.key).map((d) => (
                <motion.div
                  key={d.id}
                  layout
                  draggable
                  onDragStart={() => setDragged(d)}
                  onDragEnd={() => setDragged(null)}
                  className="bg-white rounded-xl border border-slate-200 p-3 cursor-grab active:cursor-grabbing hover:shadow-md hover:-translate-y-0.5 transition-transform"
                  data-testid={`deal-${d.id}`}
                >
                  <div className="text-[13px] font-semibold text-slate-900 leading-snug">{d.title}</div>
                  <div className="text-[11.5px] text-slate-500 mt-0.5">{d.customerName}</div>
                  {d.customerPhone && <div className="text-[10.5px] text-slate-400">📞 {d.customerPhone}</div>}
                  {d.source === "glczone.in" && <div className="text-[10px] mt-1 inline-block bg-green-50 text-green-700 px-1.5 py-0.5 rounded font-medium">GlcZone Order</div>}
                  <div className="mt-2.5 flex items-center justify-between">
                    <div className="font-mono tabular text-[13px] font-semibold text-slate-900">{fmtInr(d.value)}</div>
                    <div className="text-[10.5px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{d.probability}%</div>
                  </div>
                  {d.paymentStatus && <div className={`text-[10px] mt-1 font-medium ${d.paymentStatus==="paid"?"text-green-600":"text-orange-500"}`}>💳 {d.paymentStatus.toUpperCase()}</div>}
                  {d.expectedClose && <div className="text-[10.5px] text-slate-400 mt-1">🗓 Close · {fmtDate(d.expectedClose)}</div>}
                  {d.notes && <div className="text-[10.5px] text-slate-400 mt-1 truncate">📝 {d.notes}</div>}
                </motion.div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle>Add Deal</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Deal Title*" v={form.title} on={(v) => setForm({ ...form, title: v })} tid="deal-title" />
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Select Customer (CRM)</label>
              <select onChange={(e) => fillCustomer(e.target.value)} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                <option value="">— Pick from CRM or type below —</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.name} {c.phone ? `(${c.phone})` : ""}</option>)}
              </select>
            </div>
            <Field label="Customer Name" v={form.customerName} on={(v) => setForm({ ...form, customerName: v })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Value ₹" v={form.value} on={(v) => setForm({ ...form, value: Number(v) })} type="number" />
              <Field label="Probability %" v={form.probability} on={(v) => setForm({ ...form, probability: Number(v) })} type="number" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-500 mb-1 block">Stage</label>
                <select value={form.stage} onChange={(e) => setForm({...form, stage: e.target.value})} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                  {[{key:"NEW",label:"New"},{key:"CONTACTED",label:"Contacted"},{key:"QUALIFIED",label:"Qualified"},{key:"PROPOSAL",label:"Proposal"},{key:"NEGOTIATION",label:"Negotiation"},{key:"WON",label:"Won"}].map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              </div>
              <Field label="Expected Close Date" v={form.expectedClose} on={(v) => setForm({ ...form, expectedClose: v })} type="date" />
            </div>
            <Field label="Notes" v={form.notes} on={(v) => setForm({ ...form, notes: v })} />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-deal" onClick={save} disabled={!form.title} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Add</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
