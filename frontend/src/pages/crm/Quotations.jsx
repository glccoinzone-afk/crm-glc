import React, { useEffect, useState } from "react";
import { Plus, ArrowRight, FileText } from "lucide-react";
import { toast } from "sonner";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";

export default function Quotations() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({ customerName: "", customerGst: "", customerState: "Delhi", items: [] });

  const load = () => {
    setLoading(true);
    api.get("/quotations").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); api.get("/products", { params: { limit: 100 } }).then((r) => setProducts(r.data.items || [])); }, []);

  const addItem = () => setForm({ ...form, items: [...form.items, { productId: "", name: "", hsn: "", qty: 1, rate: 0, discount: 0, gstRate: 18 }] });
  const setItem = (i, key, val) => {
    const items = [...form.items];
    if (key === "productId") {
      const p = products.find((x) => x.id === val);
      if (p) { items[i] = { ...items[i], productId: p.id, name: p.name, hsn: p.hsn, rate: p.sellingPrice, gstRate: p.gstRate }; }
      else items[i][key] = val;
    } else items[i][key] = ["qty", "rate", "discount", "gstRate"].includes(key) ? Number(val) : val;
    setForm({ ...form, items });
  };

  const subtotal = form.items.reduce((s, i) => s + (i.qty * i.rate) * (1 - (i.discount || 0) / 100), 0);
  const tax = form.items.reduce((s, i) => s + (i.qty * i.rate) * (1 - (i.discount || 0) / 100) * (i.gstRate / 100), 0);
  const grand = subtotal + tax;

  const save = async () => {
    if (!form.customerName || form.items.length === 0) return toast.error("Add customer & at least one line item");
    await api.post("/quotations", form);
    toast.success("Quotation created");
    setOpen(false);
    setForm({ customerName: "", customerGst: "", customerState: "Delhi", items: [] });
    load();
  };
  const convert = async (q) => {
    await api.post(`/quotations/${q.id}/convert`);
    toast.success(`${q.quoteNo} converted to Sales Order`);
    load();
  };

  const columns = [
    { key: "quoteNo", header: "Quote", mono: true, render: (r) => <span className="font-medium">{r.quoteNo}</span> },
    { key: "customerName", header: "Customer" },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
    { key: "actions", header: "", align: "right", render: (r) => (
        r.status !== "CONVERTED" ? <button data-testid={`quote-convert-${r.id}`} onClick={() => convert(r)} className="text-[12px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1">Convert to Order <ArrowRight size={12} /></button> : <span className="text-[11.5px] text-emerald-600">Order created</span>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        testId="quotations-page"
        title="Quotations"
        subtitle="Draft, GST-calculate and convert quotes to orders in one click"
        actions={
          <button data-testid="new-quote-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Plus size={14} /> New Quotation
          </button>
        }
      />
      {(!loading && rows.length === 0) ? (
        <EmptyState icon={FileText} title="No quotations yet" description="Create a quotation with GST breakup and share as PDF." />
      ) : <DataGrid columns={columns} rows={rows} loading={loading} testId="quotes-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="new-quote-dialog" className="max-w-3xl rounded-2xl">
          <DialogHeader><DialogTitle>New Quotation</DialogTitle></DialogHeader>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Customer Name*" v={form.customerName} on={(v) => setForm({ ...form, customerName: v })} tid="quote-customer" />
            <Field label="Customer GSTIN" v={form.customerGst} on={(v) => setForm({ ...form, customerGst: v })} />
            <Field label="Customer State" v={form.customerState} on={(v) => setForm({ ...form, customerState: v })} />
          </div>
          <div className="mt-3 border border-slate-100 rounded-xl overflow-hidden">
            <div className="bg-slate-50 px-3 py-2 flex items-center justify-between">
              <div className="text-[12px] font-semibold text-slate-700">Line Items</div>
              <button onClick={addItem} className="text-[12px] text-[hsl(var(--primary))] font-medium">+ Add item</button>
            </div>
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-wide text-slate-500 border-b border-slate-100">
                  <th className="px-3 py-2">Product</th><th className="px-2 py-2 text-right">Qty</th><th className="px-2 py-2 text-right">Rate</th><th className="px-2 py-2 text-right">GST%</th><th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {form.items.map((it, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    <td className="px-3 py-2">
                      <select value={it.productId} onChange={(e) => setItem(i, "productId", e.target.value)} className="w-full h-9 px-2 rounded-md border border-slate-200 text-[12.5px] bg-white">
                        <option value="">Select…</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-2"><input value={it.qty} onChange={(e) => setItem(i, "qty", e.target.value)} type="number" className="w-16 h-9 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                    <td className="px-2 py-2"><input value={it.rate} onChange={(e) => setItem(i, "rate", e.target.value)} type="number" className="w-24 h-9 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                    <td className="px-2 py-2"><input value={it.gstRate} onChange={(e) => setItem(i, "gstRate", e.target.value)} type="number" className="w-16 h-9 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                    <td className="px-3 py-2 text-right font-mono text-[12px]">{fmtInr(it.qty * it.rate)}</td>
                  </tr>
                ))}
                {form.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">Add your first line item.</td></tr>}
              </tbody>
            </table>
            <div className="px-4 py-3 bg-slate-50 border-t border-slate-100 flex justify-end gap-8 text-[12.5px]">
              <div>Subtotal: <span className="font-mono tabular text-slate-900">{fmtInr(subtotal)}</span></div>
              <div>Tax: <span className="font-mono tabular text-slate-900">{fmtInr(tax)}</span></div>
              <div className="font-semibold">Grand: <span className="font-mono tabular text-slate-900">{fmtInr(grand)}</span></div>
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-quote" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Create Quotation</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
