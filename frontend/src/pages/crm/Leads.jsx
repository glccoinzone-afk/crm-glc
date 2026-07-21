import React, { useEffect, useState } from "react";
import { Plus, Search, UserSquare2, Trash2, ArrowRight } from "lucide-react";
import api, { fmtDate, fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

const SOURCES = ["MANUAL", "WEBSITE", "WHATSAPP", "REFERRAL", "CAMPAIGN", "SOCIAL", "COLD_CALL"];
const STATUSES = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

const empty = { name: "", email: "", phone: "", company: "", source: "MANUAL", status: "NEW", score: 40, value: 0, notes: "", tags: [] };

export default function Leads() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    const params = {};
    if (q) params.q = q;
    if (status) params.status = status;
    api.get("/leads", { params }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(load, [q, status]);

  const save = async () => {
    setSaving(true);
    try {
      await api.post("/leads", form);
      toast.success("Lead created");
      setOpen(false);
      setForm(empty);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setSaving(false);
  };

  const convert = async (r) => {
    try { await api.post(`/leads/${r.id}/convert`); toast.success(`${r.name} converted to customer`); load(); }
    catch { toast.error("Convert failed"); }
  };
  const del = async (r) => {
    if (!window.confirm(`Delete lead "${r.name}"?`)) return;
    await api.delete(`/leads/${r.id}`); toast.success("Deleted"); load();
  };

  const columns = [
    { key: "name", header: "Lead", render: (r) => (
        <div>
          <div className="font-medium text-slate-900">{r.name}</div>
          <div className="text-[11.5px] text-slate-500">{r.company || "—"}</div>
        </div>
      )
    },
    { key: "contact", header: "Contact", render: (r) => (
        <div>
          <div className="text-slate-800 text-[12.5px]">{r.email || "—"}</div>
          <div className="text-slate-500 text-[11.5px]">{r.phone || "—"}</div>
        </div>
      )
    },
    { key: "source", header: "Source", render: (r) => <span className="text-[11.5px] text-slate-600 uppercase tracking-wide">{r.source}</span> },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "score", header: "Score", mono: true, render: (r) => (
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-[hsl(var(--primary))]" style={{ width: `${r.score || 0}%` }} />
          </div>
          <span className="text-[12px]">{r.score || 0}</span>
        </div>
      )
    },
    { key: "value", header: "Deal Value", mono: true, align: "right", render: (r) => fmtInr(r.value) },
    { key: "vertical", header: "Vertical", render: (r) => <span className="text-[11.5px] text-slate-600">{r.vertical || "—"}</span> },
    { key: "actions", header: "", align: "right", render: (r) => (
        <div className="flex items-center gap-1 justify-end">
          <button data-testid={`lead-convert-${r.id}`} onClick={(e) => { e.stopPropagation(); convert(r); }} title="Convert" className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-emerald-600">
            <ArrowRight size={14} />
          </button>
          <button data-testid={`lead-delete-${r.id}`} onClick={(e) => { e.stopPropagation(); del(r); }} title="Delete" className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-rose-600">
            <Trash2 size={14} />
          </button>
        </div>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        testId="leads-page"
        title="Leads"
        subtitle="Track and qualify prospective customers across every vertical"
        actions={
          <button data-testid="new-lead-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Plus size={14} /> New Lead
          </button>
        }
      />
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input data-testid="lead-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, phone, email…" className="w-full h-10 pl-9 pr-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
        </div>
        <select data-testid="lead-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {(!loading && rows.length === 0) ? (
        <EmptyState icon={UserSquare2} title="No leads yet" description="Start adding leads to build your sales pipeline." action={
          <button onClick={() => setOpen(true)} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Add Your First Lead</button>
        }/>
      ) : (
        <DataGrid columns={columns} rows={rows} loading={loading} testId="leads-grid" />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="new-lead-dialog" className="max-w-lg rounded-2xl">
          <DialogHeader>
            <DialogTitle>New Lead</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="lead-name" />
            <Field label="Company" v={form.company} on={(v) => setForm({ ...form, company: v })} tid="lead-company" />
            <Field label="Email" v={form.email} on={(v) => setForm({ ...form, email: v })} tid="lead-email" />
            <Field label="Phone" v={form.phone} on={(v) => setForm({ ...form, phone: v })} tid="lead-phone" />
            <SelectField label="Source" v={form.source} on={(v) => setForm({ ...form, source: v })} opts={SOURCES} />
            <SelectField label="Status" v={form.status} on={(v) => setForm({ ...form, status: v })} opts={STATUSES} />
            <Field label="Score" v={form.score} on={(v) => setForm({ ...form, score: Number(v) })} type="number" />
            <Field label="Deal Value ₹" v={form.value} on={(v) => setForm({ ...form, value: Number(v) })} type="number" />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-lead" onClick={save} disabled={saving || !form.name} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] disabled:opacity-60">
              {saving ? "Saving…" : "Create Lead"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function Field({ label, v, on, type = "text", tid }) {
  return (
    <label className="text-[11.5px] font-medium text-slate-600 col-span-1">
      {label}
      <input data-testid={tid} value={v ?? ""} onChange={(e) => on(e.target.value)} type={type} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
    </label>
  );
}
export function SelectField({ label, v, on, opts }) {
  return (
    <label className="text-[11.5px] font-medium text-slate-600">
      {label}
      <select value={v} onChange={(e) => on(e.target.value)} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white outline-none focus:border-[hsl(var(--primary))]">
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
