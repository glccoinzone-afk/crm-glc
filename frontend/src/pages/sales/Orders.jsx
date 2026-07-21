import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Receipt, Trash2 } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { toast } from "sonner";

export default function Orders() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");

  const load = () => {
    setLoading(true);
    api.get("/orders", { params: status ? { status } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  };
  useEffect(load, [status]);

  const genInvoice = async (o) => {
    try { const r = await api.post(`/orders/${o.id}/invoice`); toast.success(`Invoice ${r.data.invoiceNo || "generated"}`); nav("/sales/invoices"); }
    catch { toast.error("Failed"); }
  };
  const del = async (o) => {
    if (!window.confirm(`Delete order ${o.orderNo}?`)) return;
    await api.delete(`/orders/${o.id}`); toast.success("Deleted"); load();
  };

  const columns = [
    { key: "orderNo", header: "Order", mono: true, render: (r) => <span className="font-medium">{r.orderNo}</span> },
    { key: "customerName", header: "Customer" },
    { key: "vertical", header: "Vertical", render: (r) => r.vertical || r.store || "—" },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
    { key: "actions", header: "", align: "right", render: (r) => (
        <div className="flex items-center gap-1 justify-end">
          <button data-testid={`order-invoice-${r.id}`} onClick={(e) => { e.stopPropagation(); genInvoice(r); }} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline">Invoice</button>
          <button data-testid={`order-delete-${r.id}`} onClick={(e) => { e.stopPropagation(); del(r); }} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-rose-600"><Trash2 size={14} /></button>
        </div>
      )
    },
  ];

  const STATUSES = ["", "PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"];

  return (
    <div className="space-y-6">
      <PageHeader testId="orders-page" title="Sales Orders" subtitle="Confirm, fulfill and invoice orders across every store" />
      <div className="flex gap-2">
        <select data-testid="orders-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none">
          {STATUSES.map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}
        </select>
      </div>
      {(!loading && rows.length === 0) ? (
        <EmptyState icon={Receipt} title="No orders yet" description="Create quotations and convert them into orders." />
      ) : <DataGrid columns={columns} rows={rows} loading={loading} testId="orders-grid" />}
    </div>
  );
}
