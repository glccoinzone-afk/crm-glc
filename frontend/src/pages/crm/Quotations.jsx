import React, { useEffect, useState } from "react";
import { Plus, ArrowRight, FileText, Download, Share2, Trash2, Phone, Mail, MapPin, Building2, Send } from "lucide-react";
import { toast } from "sonner";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";

const GST_CATEGORIES = [
  { label: "Fresh Vegetables", gst: 0, hsn: "0701", unit: "KG" },
  { label: "Fresh Fruits", gst: 0, hsn: "0801", unit: "KG" },
  { label: "Dry Fruits", gst: 12, hsn: "0801", unit: "KG" },
  { label: "Grains / Cereals / Rice", gst: 0, hsn: "1001", unit: "KG" },
  { label: "Flour / Atta / Maida", gst: 0, hsn: "1101", unit: "KG" },
  { label: "Milk / Curd / Lassi", gst: 0, hsn: "0401", unit: "LTR" },
  { label: "Paneer / Cheese / Butter", gst: 12, hsn: "0406", unit: "KG" },
  { label: "Edible Oil", gst: 5, hsn: "1507", unit: "LTR" },
  { label: "Sugar / Jaggery", gst: 5, hsn: "1701", unit: "KG" },
  { label: "Tea / Coffee", gst: 5, hsn: "0902", unit: "KG" },
  { label: "Spices / Masala", gst: 5, hsn: "0904", unit: "KG" },
  { label: "Packaged / Processed Food", gst: 12, hsn: "2001", unit: "PCS" },
  { label: "Beverages (Non-Alcoholic)", gst: 12, hsn: "2202", unit: "LTR" },
  { label: "Seeds / Saplings", gst: 0, hsn: "1201", unit: "KG" },
  { label: "Fertilizers / Pesticides", gst: 5, hsn: "3101", unit: "KG" },
  { label: "Medicines / Pharma", gst: 12, hsn: "3004", unit: "PCS" },
  { label: "Soap / Detergent / Shampoo", gst: 18, hsn: "3401", unit: "PCS" },
  { label: "Clothing (below ₹1000)", gst: 5, hsn: "6101", unit: "PCS" },
  { label: "Clothing (above ₹1000)", gst: 12, hsn: "6101", unit: "PCS" },
  { label: "Footwear (below ₹1000)", gst: 5, hsn: "6401", unit: "PCS" },
  { label: "Footwear (above ₹1000)", gst: 12, hsn: "6401", unit: "PCS" },
  { label: "Furniture / Home Furnishing", gst: 18, hsn: "9401", unit: "PCS" },
  { label: "Electronics / Appliances", gst: 18, hsn: "8501", unit: "PCS" },
  { label: "Mobile Phones", gst: 18, hsn: "8517", unit: "PCS" },
  { label: "Stationery / Books (taxable)", gst: 12, hsn: "4817", unit: "PCS" },
  { label: "Hardware / Tools", gst: 18, hsn: "8201", unit: "PCS" },
  { label: "Paints / Varnish", gst: 18, hsn: "3208", unit: "LTR" },
  { label: "Cement / Construction", gst: 28, hsn: "2523", unit: "BAG" },
  { label: "Iron / Steel / Metal", gst: 18, hsn: "7201", unit: "KG" },
  { label: "Jewellery / Gold", gst: 3, hsn: "7101", unit: "PCS" },
  { label: "Plastic / Rubber Goods", gst: 18, hsn: "3901", unit: "PCS" },
  { label: "Paper / Cardboard", gst: 12, hsn: "4801", unit: "KG" },
  { label: "Wood / Timber", gst: 18, hsn: "4401", unit: "CFT" },
  { label: "Services (General)", gst: 18, hsn: "9983", unit: "NOS" },
  { label: "Professional Services", gst: 18, hsn: "9983", unit: "NOS" },
  { label: "Transport / Freight", gst: 5, hsn: "9965", unit: "NOS" },
  { label: "Other / Custom", gst: 18, hsn: "", unit: "PCS" },
];

const STATES = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Jammu and Kashmir","Ladakh"];

export default function Quotations() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({
    customerName: "", customerPhone: "", customerEmail: "",
    customerGst: "", customerState: "Bihar", customerAddress: "",
    companyName: "", validDays: 30, notes: "", terms: "Payment due within 30 days.",
    items: []
  });
  const [customers, setCustomers] = useState([]);
  useEffect(() => {
    api.get("/customers", { params: { limit: 100 } }).then((r) => setCustomers(r.data.items || []));
  }, []);
  const fillCustomer = (cid) => {
    const c = customers.find((x) => x.id === cid);
    if (c) setForm((f) => ({ ...f, customerName: c.name, customerPhone: c.phone || "", customerEmail: c.email || "", companyName: c.company || "" }));
  };

  const load = () => {
    setLoading(true);
    api.get("/quotations").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); api.get("/products", { params: { limit: 100 } }).then((r) => setProducts(r.data.items || [])); }, []);

  const addItem = () => setForm({ ...form, items: [...form.items, { productId: "", name: "", hsn: "", qty: 1, unit: "KG", rate: 0, discount: 0, gstRate: 0 }] });
  const setItem = (i, key, val) => {
    const items = [...form.items];
    if (key === "productId") {
      const p = products.find((x) => x.id === val);
      if (p) { items[i] = { ...items[i], productId: p.id, name: p.name, hsn: p.hsn || "", rate: p.sellingPrice || p.price || p.mrp || 0, gstRate: p.gstRate ?? 0, unit: p.unit || items[i].unit }; }
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
    setForm({ customerName: "", customerGst: "", customerState: "Bihar", items: [] });
    load();
  };
  const convert = async (q) => {
    await api.post(`/quotations/${q.id}/convert`);
    toast.success(`${q.quoteNo} converted to Sales Order`);
    load();
  };
  const openPdf = async (q) => {
    const token = localStorage.getItem("glc_token") || sessionStorage.getItem("glc_token") || "";
    const res = await fetch(`/crm/api/quotations/${q.id}/pdf`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const win = window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  };
  const shareWhatsApp = (q) => {
    const items = (q.items || []).map(it => `  • ${it.name} × ${it.qty} ${it.unit||""} @ ₹${it.rate}`).join("\n");
    const msg = encodeURIComponent(
      `Dear *${q.customerName}*,\n\n` +
      `Thank you for your interest in GLC Zone. Please find your quotation details below:\n\n` +
      `📋 *Quotation No:* ${q.quoteNo}\n` +
      `📅 *Date:* ${q.createdAt?.slice(0,10)||""}\n\n` +
      `*Items:*\n${items}\n\n` +
      `💰 *Grand Total: ₹${q.total?.toLocaleString("en-IN")}*\n\n` +
      `For the detailed PDF, please contact us or visit glczone.in\n\n` +
      `Thank you for your business! 🙏\n\n` +
      `— *GLC Zone Team*\n📞 +91 89691 25123\n🌐 glczone.in`
    );
    window.open(`https://wa.me/?text=${msg}`, "_blank");
  };

  const downloadPdf = async (q) => {
    const token = localStorage.getItem("glc_token") || sessionStorage.getItem("glc_token") || "";
    const res = await fetch(`/crm/api/quotations/${q.id}/pdf`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${q.quoteNo}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };

  const sendEmail = async (q) => {
    if (!q.customerEmail) return toast.error("Customer email not set on this quotation");
    try {
      await api.post(`/quotations/${q.id}/email`);
      toast.success(`Email sent to ${q.customerEmail}`);
      load();
    } catch(e) { toast.error(e?.response?.data?.detail || "Email failed"); }
  };

  const columns = [
    { key: "quoteNo", header: "Quote", mono: true, render: (r) => <span className="font-medium">{r.quoteNo}</span> },
    { key: "customerName", header: "Customer" },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
    { key: "actions", header: "", align: "right", render: (r) => (
        <div className="flex items-center gap-2 justify-end">
          <button onClick={() => openPdf(r)} title="View PDF" className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"><FileText size={12} className="text-slate-500" /></button>
          <button onClick={() => downloadPdf(r)} title="Download PDF" className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"><Download size={12} className="text-slate-500" /></button>
          <button onClick={() => shareWhatsApp(r)} title="Share on WhatsApp" className="p-1.5 rounded-lg border border-green-200 hover:bg-green-50"><Share2 size={12} className="text-green-600" /></button>
          <button onClick={() => sendEmail(r)} title="Send Email" className="p-1.5 rounded-lg border border-blue-200 hover:bg-blue-50"><Send size={12} className="text-blue-600" /></button>
          {r.status !== "CONVERTED"
            ? <button data-testid={`quote-convert-${r.id}`} onClick={() => convert(r)} className="text-[12px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1">Convert <ArrowRight size={12} /></button>
            : <span className="text-[11.5px] text-emerald-600">✓ Order</span>}
        </div>
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
        <DialogContent data-testid="new-quote-dialog" className="max-w-5xl w-full rounded-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-[16px]">New Quotation</DialogTitle>
            <p className="text-[12px] text-slate-500 mt-0.5">Fill in customer details and add line items to generate a GST-compliant quotation.</p>
          </DialogHeader>

          {/* Section 1: Customer */}
          <div className="rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5"><Building2 size={12} /> Customer Details</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-500 mb-1 block">Select Existing Customer</label>
                <select onChange={(e) => fillCustomer(e.target.value)} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                  <option value="">— Pick from CRM —</option>
                  {customers.map((c) => <option key={c.id} value={c.id}>{c.name} {c.phone ? `(${c.phone})` : ""}</option>)}
                </select>
              </div>
              <Field label="Company / Firm Name" v={form.companyName} on={(v) => setForm({ ...form, companyName: v })} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Customer Name*" v={form.customerName} on={(v) => setForm({ ...form, customerName: v })} tid="quote-customer" />
              <div className="relative"><Phone size={12} className="absolute left-2.5 top-[30px] text-slate-400" /><Field label="Phone" v={form.customerPhone} on={(v) => setForm({ ...form, customerPhone: v })} /></div>
              <div className="relative"><Mail size={12} className="absolute left-2.5 top-[30px] text-slate-400" /><Field label="Email" v={form.customerEmail} on={(v) => setForm({ ...form, customerEmail: v })} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Customer GSTIN" v={form.customerGst} on={(v) => setForm({ ...form, customerGst: v })} />
              <div>
                <label className="text-[11px] text-slate-500 mb-1 block">Customer State*</label>
                <select value={form.customerState} onChange={(e) => setForm({ ...form, customerState: e.target.value })} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                  {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <Field label="Valid For (days)" v={String(form.validDays)} on={(v) => setForm({ ...form, validDays: Number(v) })} />
            </div>
            <div className="relative"><MapPin size={12} className="absolute left-2.5 top-[30px] text-slate-400" /><Field label="Delivery Address" v={form.customerAddress} on={(v) => setForm({ ...form, customerAddress: v })} /></div>
          </div>

          {/* Section 2: Line Items */}
          <div className="rounded-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between border-b border-slate-200">
              <div className="text-[12px] font-semibold text-slate-700">Line Items</div>
              <button onClick={addItem} className="text-[12px] text-[hsl(var(--primary))] font-medium hover:underline">+ Add item</button>
            </div>
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wide text-slate-500 border-b border-slate-100 bg-slate-50/50">
                  <th className="px-3 py-2 w-[35%]">Product</th>
                  <th className="px-2 py-2">HSN</th>
                  <th className="px-2 py-2 text-right">Qty</th>
                  <th className="px-2 py-2">Unit</th>
                  <th className="px-2 py-2 text-right">Rate (₹)</th>
                  <th className="px-2 py-2 text-right">Disc%</th>
                  <th className="px-2 py-2 text-right">GST%</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {form.items.map((it, i) => {
                  const amt = it.qty * it.rate * (1 - (it.discount || 0) / 100);
                  return (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="px-3 py-1.5">
                        <select value={it.productId} onChange={(e) => setItem(i, "productId", e.target.value)} className="w-full h-8 px-2 rounded-md border border-slate-200 text-[12px] bg-white mb-1">
                          <option value="">Select product…</option>
                          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                        <select onChange={(e) => {
                          const cat = GST_CATEGORIES.find(c => c.label === e.target.value);
                          if (cat) { const items=[...form.items]; items[i]={...items[i], hsn: cat.hsn, gstRate: cat.gst, unit: cat.unit}; setForm({...form, items}); }
                        }} className="w-full h-7 px-2 rounded-md border border-slate-100 text-[11px] bg-slate-50 text-slate-500">
                          <option value="">— GST category —</option>
                          {GST_CATEGORIES.map(c => <option key={c.label} value={c.label}>{c.label} ({c.gst}%)</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5"><input value={it.hsn||""} onChange={(e) => setItem(i, "hsn", e.target.value)} className="w-16 h-8 px-2 rounded-md border border-slate-200 font-mono text-[11px]" placeholder="HSN" /></td>
                      <td className="px-2 py-1.5"><input value={it.qty} onChange={(e) => setItem(i, "qty", e.target.value)} type="number" min="1" className="w-14 h-8 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                      <td className="px-2 py-1.5">
                        <select value={it.unit||"KG"} onChange={(e) => setItem(i, "unit", e.target.value)} className="w-16 h-8 px-1 rounded-md border border-slate-200 text-[11px] bg-white">
                          {["KG","PCS","LTR","BOX","BAG","MTR","NOS"].map(u => <option key={u}>{u}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5"><input value={it.rate} onChange={(e) => setItem(i, "rate", e.target.value)} type="number" className="w-20 h-8 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                      <td className="px-2 py-1.5"><input value={it.discount||0} onChange={(e) => setItem(i, "discount", e.target.value)} type="number" min="0" max="100" className="w-14 h-8 px-2 rounded-md border border-slate-200 text-right font-mono text-[12px]" /></td>
                      <td className="px-2 py-1.5">
                        <select value={it.gstRate||0} onChange={(e) => setItem(i, "gstRate", Number(e.target.value))} className="w-16 h-8 px-1 rounded-md border border-slate-200 text-[11px] bg-white">
                          {[0,5,12,18,28].map(r => <option key={r} value={r}>{r}%</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono text-[12px] font-medium">{fmtInr(amt)}</td>
                      <td className="px-2 py-1.5"><button onClick={() => setForm({...form, items: form.items.filter((_,j)=>j!==i)})} className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500"><Trash2 size={12}/></button></td>
                    </tr>
                  );
                })}
                {form.items.length === 0 && <tr><td colSpan={9} className="px-3 py-8 text-center text-slate-400 text-[12px]">Click "+ Add item" to add products.</td></tr>}
              </tbody>
            </table>
            <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex justify-end gap-6 text-[12.5px]">
              <div className="text-slate-600">Subtotal: <span className="font-mono font-semibold text-slate-900">{fmtInr(subtotal)}</span></div>
              <div className="text-slate-600">GST: <span className="font-mono font-semibold text-slate-900">{fmtInr(tax)}</span></div>
              <div className="text-slate-800 font-bold text-[14px]">Grand Total: <span className="font-mono text-[hsl(var(--primary))]">{fmtInr(grand)}</span></div>
            </div>
          </div>

          {/* Section 3: Notes & Terms */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Notes (visible to customer)</label>
              <textarea value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} rows={3} placeholder="e.g. Delivery in 2-3 days, inclusive of packaging..." className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[12.5px] resize-none outline-none focus:border-[hsl(var(--primary))]" />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Terms & Conditions</label>
              <textarea value={form.terms} onChange={(e) => setForm({...form, terms: e.target.value})} rows={3} className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[12.5px] resize-none outline-none focus:border-[hsl(var(--primary))]" />
            </div>
          </div>

          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-4 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100 border border-slate-200">Cancel</button>
            <button data-testid="save-quote" onClick={save} className="px-5 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] font-medium">Create Quotation</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
