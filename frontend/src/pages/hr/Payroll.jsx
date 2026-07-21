import React, { useEffect, useRef, useState } from "react";
import { Wallet, Play, Printer, X } from "lucide-react";
import { useReactToPrint } from "react-to-print";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { toast } from "sonner";

export default function Payroll() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [slipOpen, setSlipOpen] = useState(false);
  const [slip, setSlip] = useState(null);

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
    { key: "actions", header: "", align: "right", render: (r) => (
        <button data-testid={`payslip-${r.id}`} onClick={() => { setSlip(r); setSlipOpen(true); }} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1"><Printer size={12} /> Payslip</button>
      )
    },
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

      <Dialog open={slipOpen} onOpenChange={setSlipOpen}>
        <DialogContent className="max-w-xl rounded-2xl p-0 overflow-hidden">
          {slip && <PayslipView slip={slip} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PayslipView({ slip }) {
  const ref = useRef(null);
  const print = useReactToPrint({ contentRef: ref, documentTitle: `Payslip-${slip.employeeName}-${slip.month}` });
  const total = slip.basic;
  const gross = slip.basic;
  return (
    <div>
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-slate-100">
        <div className="text-[13px] font-semibold text-slate-500">Payslip Preview</div>
        <button data-testid="payslip-print" onClick={print} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          <Printer size={13} /> Print / PDF
        </button>
      </div>
      <div ref={ref} className="p-8 bg-white">
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Payslip</div>
            <div className="text-[22px] font-semibold tracking-tight text-slate-900 mt-0.5">{slip.month}</div>
            <div className="text-[12px] text-slate-500 mt-0.5">Employee: <span className="font-semibold text-slate-800">{slip.employeeName}</span></div>
          </div>
          <div className="text-right">
            <div className="text-[15px] font-semibold text-slate-900">GLC Zone Pvt Ltd</div>
            <div className="text-[11.5px] text-slate-500">New Delhi, India</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 mt-6">
          <div>
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-slate-500 mb-2">Earnings</div>
            <Row k="Basic Salary" v={fmtInr(slip.basic)} />
            <div className="border-t border-slate-100 mt-2 pt-2 flex justify-between font-semibold text-[13px]">
              <span>Gross</span><span className="font-mono tabular">{fmtInr(gross)}</span>
            </div>
          </div>
          <div>
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-slate-500 mb-2">Deductions</div>
            <Row k="Provident Fund (12%)" v={fmtInr(slip.pf)} />
            <Row k="ESI (1.75%)" v={fmtInr(slip.esi)} />
            <Row k="TDS" v={fmtInr(slip.tds)} />
            <div className="border-t border-slate-100 mt-2 pt-2 flex justify-between font-semibold text-[13px]">
              <span>Total Deductions</span><span className="font-mono tabular">{fmtInr(slip.pf + slip.esi + slip.tds)}</span>
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-xl bg-[hsl(158_64%_96%)] p-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wide font-semibold text-[hsl(var(--primary))]">Net Salary</div>
            <div className="text-[10.5px] text-slate-500">Credited to registered bank account</div>
          </div>
          <div className="text-[26px] font-semibold text-slate-900 font-mono tabular">{fmtInr(slip.netSalary)}</div>
        </div>

        <div className="mt-6 text-[10.5px] text-slate-400 text-center pt-3 border-t border-slate-100">
          This is a computer-generated payslip. GLC Zone Private Limited · New Delhi, India.
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }) { return <div className="flex justify-between text-slate-700 text-[13px] py-1"><span>{k}</span><span className="font-mono tabular">{v}</span></div>; }
