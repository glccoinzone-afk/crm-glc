import React, { useEffect, useState } from "react";
import { Plus, Search, Users, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/pages/crm/Leads";
import { toast } from "sonner";

const TYPES = ["RETAIL", "WHOLESALE", "DISTRIBUTOR"];

export default function Customers() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", company: "", gst: "", pan: "", type: "RETAIL", creditLimit: 0, state: "" });

  const load = () => {
    setLoading(true);
    api.get("/customers", { params: q ? { q } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(load, [q]);

  const save = async () => {
    try { await api.post("/customers", form); toast.success("Customer created"); setOpen(false); load(); }
    catch { toast.error("Failed to create customer"); }
  };

  const del = async (r) => {
    if (!window.confirm(`Delete ${r.name}?`)) return;
    await api.delete(`/customers/${r.id}`); toast.success("Deleted"); load();
  };

  const columns = [
    { key: "name", header: "Customer", render: (r) => (
        <div>
          <div className="font-medium text-slate-900">{r.name}</div>
          <div className="text-[11.5px] text-slate-500">{r.company || "—"}</div>
        </div>
      )
    },
    { key: "contact", header: "Contact", render: (r) => (
        <div>
          <div className="text-[12.5px] text-slate-800">{r.email || "—"}</div>
          <div className="text-[11.5px] text-slate-500">{r.phone || "—"}</div>
        </div>
      )
    },
    { key: "gst", header: "GSTIN", mono: true, render: (r) => r.gst || "—" },
    { key: "type", header: "Type", render: (r) => <span className="text-[11.5px] text-slate-600 uppercase tracking-wide">{r.type}</span> },
    { key: "vertical", header: "Vertical", render: (r) => r.vertical || "—" },
    { key: "creditLimit", header: "Credit Limit", mono: true, align: "right", render: (r) => fmtInr(r.creditLimit) },
    { key: "actions", header: "", align: "right", render: (r) => (
        <button data-testid={`cust-delete-${r.id}`} onClick={(e) => { e.stopPropagation(); del(r); }} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-rose-600"><Trash2 size={14} /></button>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        testId="customers-page"
        title="Customers"
        subtitle="360° view of every customer relationship"
        actions={
          <button data-testid="new-customer-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Plus size={14} /> New Customer
          </button>
        }
      />
      <div className="relative max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input data-testid="customer-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search customers…" className="w-full h-10 pl-9 pr-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
      </div>
      {(!loading && rows.length === 0) ? (
        <EmptyState icon={Users} title="No customers yet" description="Add your first customer to start tracking sales history." />
      ) : (
        <DataGrid columns={columns} rows={rows} loading={loading} testId="customers-grid" onRowClick={(r) => nav(`/crm/customers/${r.id}`)} />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Customer</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="cust-name" />
            <Field label="Company" v={form.company} on={(v) => setForm({ ...form, company: v })} />
            <Field label="Email" v={form.email} on={(v) => setForm({ ...form, email: v })} />
            <Field label="Phone" v={form.phone} on={(v) => setForm({ ...form, phone: v })} />
            <Field label="GSTIN" v={form.gst} on={(v) => setForm({ ...form, gst: v })} />
            <Field label="PAN" v={form.pan} on={(v) => setForm({ ...form, pan: v })} />
            <SelectField label="Type" v={form.type} on={(v) => setForm({ ...form, type: v })} opts={TYPES} />
            <Field label="Credit Limit ₹" v={form.creditLimit} on={(v) => setForm({ ...form, creditLimit: Number(v) })} type="number" />
            <Field label="State" v={form.state} on={(v) => setForm({ ...form, state: v })} />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-customer" onClick={save} disabled={!form.name} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] disabled:opacity-60">Create</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
