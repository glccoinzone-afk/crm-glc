import React, { useEffect, useState } from "react";
import { ClipboardList, ArrowRight } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { toast } from "sonner";

export default function PurchaseOrders() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => { setLoading(true); api.get("/purchase-orders").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);

  const receive = async (r) => {
    await api.put(`/purchase-orders/${r.id}`, { status: "RECEIVED" });
    toast.success(`${r.poNo} marked received; stock updated`);
    load();
  };

  const columns = [
    { key: "poNo", header: "PO", mono: true, render: (r) => <span className="font-medium">{r.poNo}</span> },
    { key: "supplierName", header: "Supplier" },
    { key: "createdAt", header: "Date", render: (r) => fmtDate(r.createdAt) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
    { key: "actions", header: "", align: "right", render: (r) => (
        r.status !== "RECEIVED" ? <button data-testid={`po-receive-${r.id}`} onClick={() => receive(r)} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1">Mark Received <ArrowRight size={11}/></button> : <span className="text-[11.5px] text-emerald-600">Stock updated</span>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="pos-page" title="Purchase Orders" subtitle="Draft POs, receive stock via GRN, and reconcile bills" />
      {(!loading && rows.length === 0) ? <EmptyState icon={ClipboardList} title="No purchase orders yet" description="Create POs to procure inventory from suppliers." /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="pos-grid" />}
    </div>
  );
}
