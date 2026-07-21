import React, { useEffect, useState } from "react";
import { Plus, Building2 } from "lucide-react";
import api from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";
import { toast } from "sonner";

export default function Suppliers() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", gst: "", pan: "", phone: "", email: "", paymentTerms: "Net 30" });

  const load = () => { setLoading(true); api.get("/suppliers").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);

  const save = async () => { await api.post("/suppliers", form); toast.success("Supplier added"); setOpen(false); load(); };

  const columns = [
    { key: "name", header: "Supplier", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "gst", header: "GSTIN", mono: true },
    { key: "email", header: "Email" },
    { key: "phone", header: "Phone" },
    { key: "vertical", header: "Vertical" },
    { key: "rating", header: "Rating", mono: true, align: "right", render: (r) => `${(r.rating || 0).toFixed(1)}★` },
    { key: "paymentTerms", header: "Terms" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="suppliers-page" title="Suppliers" subtitle="Manage vendors, ratings, and payment terms" actions={
        <button data-testid="new-supplier-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          <Plus size={14} /> New Supplier
        </button>
      }/>
      {(!loading && rows.length === 0) ? <EmptyState icon={Building2} title="No suppliers" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="suppliers-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Supplier</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="sup-name" />
            <Field label="GSTIN" v={form.gst} on={(v) => setForm({ ...form, gst: v })} />
            <Field label="Email" v={form.email} on={(v) => setForm({ ...form, email: v })} />
            <Field label="Phone" v={form.phone} on={(v) => setForm({ ...form, phone: v })} />
            <Field label="PAN" v={form.pan} on={(v) => setForm({ ...form, pan: v })} />
            <Field label="Payment Terms" v={form.paymentTerms} on={(v) => setForm({ ...form, paymentTerms: v })} />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-supplier" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Create</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
