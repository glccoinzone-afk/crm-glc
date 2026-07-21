import React, { useEffect, useState } from "react";
import { Wallet, Play } from "lucide-react";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { toast } from "sonner";

export default function Payroll() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));

  const load = () => { setLoading(true); api.get("/payroll", { params: { month } }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, [month]);

  const generate = async () => {
    const r = await api.post("/payroll/generate", { month });
    toast.success(`Generated payroll for ${r.data.generated} employees`);
    load();
  };

  const columns = [
    { key: "employeeName", header: "Employee" },
    { key: "month", header: "Month", mono: true },
    { key: "basic", header: "Basic", mono: true, align: "right", render: (r) => fmtInr(r.basic) },
    { key: "pf", header: "PF", mono: true, align: "right", render: (r) => fmtInr(r.pf) },
    { key: "esi", header: "ESI", mono: true, align: "right", render: (r) => fmtInr(r.esi) },
    { key: "tds", header: "TDS", mono: true, align: "right", render: (r) => fmtInr(r.tds) },
    { key: "netSalary", header: "Net", mono: true, align: "right", render: (r) => <span className="font-semibold text-slate-900">{fmtInr(r.netSalary)}</span> },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="payroll-page" title="Payroll" subtitle="Generate monthly payroll with PF, ESI, TDS auto-calculation" actions={
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white" />
          <button data-testid="run-payroll" onClick={generate} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Play size={13} /> Run Payroll
          </button>
        </div>
      }/>
      {(!loading && rows.length === 0) ? <EmptyState icon={Wallet} title="No payroll for this month" description="Click 'Run Payroll' to generate salary slips." /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="payroll-grid" />}
    </div>
  );
}
