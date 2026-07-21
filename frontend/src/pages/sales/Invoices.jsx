import React, { useEffect, useState } from "react";
import { Receipt, IndianRupee } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/pages/crm/Leads";
import { toast } from "sonner";

const METHODS = ["CASH", "UPI", "CARD", "NEFT", "RTGS", "CHEQUE"];

export default function Invoices() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [payOpen, setPayOpen] = useState(false);
  const [payFor, setPayFor] = useState(null);
  const [pay, setPay] = useState({ amount: 0, method: "UPI", reference: "" });
  const [viewOpen, setViewOpen] = useState(false);
  const [viewInv, setViewInv] = useState(null);

  const load = () => {
    setLoading(true);
    api.get("/invoices", { params: status ? { status } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(load, [status]);

  const openPay = (r) => { setPayFor(r); setPay({ amount: r.dueAmount || 0, method: "UPI", reference: "" }); setPayOpen(true); };
  const savePay = async () => {
    try {
      await api.post("/payments", { invoiceId: payFor.id, amount: Number(pay.amount), method: pay.method, reference: pay.reference });
      toast.success("Payment recorded");
      setPayOpen(false); load();
    } catch { toast.error("Failed"); }
  };

  const view = (r) => { setViewInv(r); setViewOpen(true); };

  const columns = [
    { key: "invoiceNo", header: "Invoice", mono: true, render: (r) => <span className="font-medium">{r.invoiceNo}</span> },
    { key: "customerName", header: "Customer" },
    { key: "invoiceDate", header: "Date", render: (r) => fmtDate(r.invoiceDate) },
    { key: "dueDate", header: "Due", render: (r) => fmtDate(r.dueDate) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
    { key: "dueAmount", header: "Due", mono: true, align: "right", render: (r) => <span className={r.dueAmount > 0 ? "text-rose-600 font-medium" : "text-slate-400"}>{fmtInr(r.dueAmount)}</span> },
    { key: "actions", header: "", align: "right", render: (r) => (
        <div className="flex items-center gap-2 justify-end">
          <button data-testid={`invoice-view-${r.id}`} onClick={(e) => { e.stopPropagation(); view(r); }} className="text-[11.5px] font-medium text-slate-600 hover:underline">View</button>
          {r.dueAmount > 0 && <button data-testid={`invoice-pay-${r.id}`} onClick={(e) => { e.stopPropagation(); openPay(r); }} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1"><IndianRupee size={11} /> Record Payment</button>}
        </div>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="invoices-page" title="GST Invoices" subtitle="India-compliant invoices with CGST / SGST / IGST breakup" />
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none w-48">
        <option value="">All statuses</option>
        <option value="UNPAID">Unpaid</option>
        <option value="PARTIAL">Partial</option>
        <option value="PAID">Paid</option>
      </select>
      {(!loading && rows.length === 0) ? (
        <EmptyState icon={Receipt} title="No invoices yet" description="Invoices appear here after you generate them from orders." />
      ) : <DataGrid columns={columns} rows={rows} loading={loading} testId="invoices-grid" />}

      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle>Record Payment</DialogTitle></DialogHeader>
          {payFor && (
            <div className="text-[13px] text-slate-600 mb-2">Invoice <span className="font-mono">{payFor.invoiceNo}</span> · Due {fmtInr(payFor.dueAmount)}</div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount ₹" v={pay.amount} on={(v) => setPay({ ...pay, amount: Number(v) })} type="number" tid="pay-amount" />
            <SelectField label="Method" v={pay.method} on={(v) => setPay({ ...pay, method: v })} opts={METHODS} />
            <Field label="Reference" v={pay.reference} on={(v) => setPay({ ...pay, reference: v })} />
          </div>
          <DialogFooter>
            <button onClick={() => setPayOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-payment" onClick={savePay} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Save Payment</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={viewOpen} onOpenChange={setViewOpen}>
        <DialogContent className="max-w-2xl rounded-2xl p-0 overflow-hidden">
          {viewInv && <InvoiceView inv={viewInv} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InvoiceView({ inv }) {
  return (
    <div className="p-8 bg-white">
      <div className="flex items-start justify-between border-b border-slate-100 pb-5">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Tax Invoice</div>
          <div className="text-[26px] font-semibold tracking-tight text-slate-900 mt-1">{inv.invoiceNo}</div>
          <div className="text-[12px] text-slate-500 mt-1">Date {fmtDate(inv.invoiceDate)} · Due {fmtDate(inv.dueDate)}</div>
        </div>
        <div className="text-right">
          <div className="text-[15px] font-semibold text-slate-900">GLC Zone Pvt Ltd</div>
          <div className="text-[11.5px] text-slate-500">GSTIN 07AABCG1234H1Z5</div>
          <div className="text-[11.5px] text-slate-500">New Delhi, India</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6 mt-5">
        <div>
          <div className="text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Bill To</div>
          <div className="text-[14px] font-semibold text-slate-900 mt-1">{inv.customerName}</div>
          {inv.customerGst && <div className="text-[11.5px] text-slate-500 font-mono">GSTIN {inv.customerGst}</div>}
          {inv.customerState && <div className="text-[11.5px] text-slate-500">{inv.customerState}</div>}
        </div>
        <div className="text-right">
          <div className="text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Amount Due</div>
          <div className="text-[26px] font-semibold text-slate-900 font-mono tabular">{fmtInr(inv.dueAmount)}</div>
          <div className="mt-1"><StatusBadge value={inv.status} /></div>
        </div>
      </div>
      <table className="w-full mt-5 text-[12.5px]">
        <thead>
          <tr className="border-b border-slate-200 text-[10.5px] uppercase tracking-wide text-slate-500">
            <th className="text-left py-2">Item</th><th className="text-left py-2">HSN</th><th className="text-right py-2">Qty</th><th className="text-right py-2">Rate</th><th className="text-right py-2">GST</th><th className="text-right py-2">Amount</th>
          </tr>
        </thead>
        <tbody>
          {(inv.items || []).map((it, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td className="py-2">{it.name}</td>
              <td className="py-2 font-mono text-[11.5px]">{it.hsn || "—"}</td>
              <td className="py-2 text-right font-mono">{it.qty}</td>
              <td className="py-2 text-right font-mono">{fmtInr(it.rate)}</td>
              <td className="py-2 text-right font-mono">{it.gstRate}%</td>
              <td className="py-2 text-right font-mono">{fmtInr(it.qty * it.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 flex justify-end">
        <div className="w-full max-w-xs text-[13px] space-y-1.5">
          <Row k="Subtotal" v={fmtInr(inv.subtotal)} />
          {inv.cgst > 0 && <Row k="CGST" v={fmtInr(inv.cgst)} />}
          {inv.sgst > 0 && <Row k="SGST" v={fmtInr(inv.sgst)} />}
          {inv.igst > 0 && <Row k="IGST" v={fmtInr(inv.igst)} />}
          <div className="border-t border-slate-200 mt-2 pt-2 flex justify-between font-semibold">
            <span>Total</span><span className="font-mono tabular">{fmtInr(inv.total)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
function Row({ k, v }) { return <div className="flex justify-between text-slate-700"><span>{k}</span><span className="font-mono tabular">{v}</span></div>; }
