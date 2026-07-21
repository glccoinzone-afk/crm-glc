import React, { useEffect, useState } from "react";
import { Plus } from "lucide-react";
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
  const [form, setForm] = useState({ title: "", customerName: "", value: 0, probability: 40, stage: "NEW" });
  const [dragged, setDragged] = useState(null);

  const load = () => api.get("/deals").then((r) => setDeals(r.data.items || []));
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
                  <div className="text-[13.5px] font-medium text-slate-900">{d.title}</div>
                  <div className="text-[11.5px] text-slate-500 mt-0.5">{d.customerName}</div>
                  <div className="mt-3 flex items-center justify-between">
                    <div className="font-mono tabular text-[13px] text-slate-900">{fmtInr(d.value)}</div>
                    <div className="text-[11px] text-slate-500">{d.probability}%</div>
                  </div>
                  {d.expectedClose && <div className="text-[10.5px] text-slate-400 mt-1">Close · {fmtDate(d.expectedClose)}</div>}
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
            <Field label="Title*" v={form.title} on={(v) => setForm({ ...form, title: v })} tid="deal-title" />
            <Field label="Customer" v={form.customerName} on={(v) => setForm({ ...form, customerName: v })} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Value ₹" v={form.value} on={(v) => setForm({ ...form, value: Number(v) })} type="number" />
              <Field label="Probability %" v={form.probability} on={(v) => setForm({ ...form, probability: Number(v) })} type="number" />
            </div>
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
