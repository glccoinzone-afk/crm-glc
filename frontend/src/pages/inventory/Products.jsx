import React, { useEffect, useState } from "react";
import { Plus, Package } from "lucide-react";
import { RefreshCw } from "lucide-react";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";
import { toast } from "sonner";

export default function Products() {
  const [rows, setRows] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [canSync, setCanSync] = useState(false);
  useEffect(() => {
    api.get("/rbac/me").then((r) => {
      const perms = r.data.modules || [];
      setCanSync(perms.includes("*") || perms.some((p) => ["inventory", "inventory.products"].includes(p)));
    });
  }, []);
  const syncNow = async () => {
    setSyncing(true);
    try {
      const r = await api.post("/sync/products");
      toast.success(`Synced: ${r.data.created} new, ${r.data.updated} updated`);
      load();
    } catch { toast.error("Sync failed"); }
    finally { setSyncing(false); }
  };
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", sku: "", category: "", hsn: "", gstRate: 18, unit: "PCS", buyingPrice: 0, sellingPrice: 0, mrp: 0, minStock: 5 });

  const load = () => { setLoading(true); api.get("/products", { params: q ? { q } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, [q]);

  const save = async () => {
    if (!form.name || !form.sku) return toast.error("Name & SKU required");
    await api.post("/products", form); toast.success("Product added"); setOpen(false); load();
  };

  const columns = [
    { key: "name", header: "Product", render: (r) => (
        <div>
          <div className="font-medium text-slate-900">{r.name}</div>
          <div className="text-[11.5px] text-slate-500 font-mono">{r.sku}</div>
        </div>
      )
    },
    { key: "category", header: "Category" },
    { key: "hsn", header: "HSN", mono: true },
    { key: "gstRate", header: "GST%", mono: true, render: (r) => `${r.gstRate}%` },
    { key: "buyingPrice", header: "Buy", mono: true, align: "right", render: (r) => fmtInr(r.buyingPrice) },
    { key: "sellingPrice", header: "Sell", mono: true, align: "right", render: (r) => fmtInr(r.sellingPrice) },
    { key: "mrp", header: "MRP", mono: true, align: "right", render: (r) => fmtInr(r.mrp) },
    { key: "minStock", header: "Min", mono: true, align: "right" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="products-page" title="Products" subtitle="Master catalog across every business vertical" actions={<div className="flex gap-2">{canSync && <button onClick={syncNow} disabled={syncing} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 text-[12.5px] font-medium hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={13} className={syncing?"animate-spin":""}/>{syncing?"Syncing…":"Sync glczone.in"}</button>}
        <button data-testid="new-product-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          <Plus size={14} /> New Product
        </button>
      </div>}/>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products…" className="w-full max-w-sm h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" data-testid="product-search" />
      {(!loading && rows.length === 0) ? <EmptyState icon={Package} title="No products yet" description="Add your first product to start selling." /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="products-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader><DialogTitle>New Product</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="prod-name" />
            <Field label="SKU*" v={form.sku} on={(v) => setForm({ ...form, sku: v })} />
            <Field label="Category" v={form.category} on={(v) => setForm({ ...form, category: v })} />
            <Field label="HSN Code" v={form.hsn} on={(v) => setForm({ ...form, hsn: v })} />
            <Field label="GST Rate %" v={form.gstRate} on={(v) => setForm({ ...form, gstRate: Number(v) })} type="number" />
            <Field label="Unit" v={form.unit} on={(v) => setForm({ ...form, unit: v })} />
            <Field label="Buying Price ₹" v={form.buyingPrice} on={(v) => setForm({ ...form, buyingPrice: Number(v) })} type="number" />
            <Field label="Selling Price ₹" v={form.sellingPrice} on={(v) => setForm({ ...form, sellingPrice: Number(v) })} type="number" />
            <Field label="MRP ₹" v={form.mrp} on={(v) => setForm({ ...form, mrp: Number(v) })} type="number" />
            <Field label="Min Stock" v={form.minStock} on={(v) => setForm({ ...form, minStock: Number(v) })} type="number" />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-product" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Create</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
