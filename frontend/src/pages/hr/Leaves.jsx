import React, { useEffect, useState } from "react";
import { CalendarClock, Check, X } from "lucide-react";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { toast } from "sonner";

export default function Leaves() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => { setLoading(true); api.get("/leaves").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);

  const act = async (r, status) => { await api.put(`/leaves/${r.id}`, { status }); toast.success(`${status}`); load(); };

  const columns = [
    { key: "employeeName", header: "Employee" },
    { key: "leaveType", header: "Type" },
    { key: "fromDate", header: "From", render: (r) => fmtDate(r.fromDate) },
    { key: "toDate", header: "To", render: (r) => fmtDate(r.toDate) },
    { key: "days", header: "Days", mono: true, align: "right" },
    { key: "reason", header: "Reason" },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "actions", header: "", align: "right", render: (r) => (
        r.status === "PENDING" ? (
          <div className="flex items-center gap-1 justify-end">
            <button data-testid={`leave-approve-${r.id}`} onClick={() => act(r, "APPROVED")} className="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-600"><Check size={14} /></button>
            <button data-testid={`leave-reject-${r.id}`} onClick={() => act(r, "REJECTED")} className="p-1.5 rounded-md hover:bg-rose-50 text-rose-600"><X size={14} /></button>
          </div>
        ) : <span className="text-[11px] text-slate-400">—</span>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="leaves-page" title="Leave Management" subtitle="Approve or reject employee leave requests" />
      {(!loading && rows.length === 0) ? <EmptyState icon={CalendarClock} title="No leave requests" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="leaves-grid" />}
    </div>
  );
}
