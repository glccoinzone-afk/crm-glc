import React, { useEffect, useState } from "react";
import { CalendarClock, Check, X, Plus } from "lucide-react";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

const LEAVE_TYPES = ["CL","EL","ML","PL","LWP","OD"];

export default function Leaves() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [emps, setEmps] = useState([]);
  const [form, setForm] = useState({ employeeId: "", employeeName: "", leaveType: "CL", fromDate: "", toDate: "", days: 1, reason: "" });

  const load = () => { setLoading(true); api.get("/leaves").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(() => {
    load();
    api.get("/employees", { params: { limit: 200 } }).then((r) => setEmps(r.data.items || []));
  }, []);

  const act = async (r, status) => { await api.put(`/leaves/${r.id}`, { status }); toast.success(`${status}`); load(); };

  const pickEmp = (eid) => {
    const e = emps.find(x => x.id === eid);
    if (e) setForm(f => ({ ...f, employeeId: e.id, employeeName: e.name }));
  };

  const calcDays = (from, to) => {
    if (!from || !to) return 1;
    const d = (new Date(to) - new Date(from)) / 86400000 + 1;
    return Math.max(1, d);
  };

  const save = async () => {
    if (!form.employeeId || !form.fromDate || !form.toDate) return toast.error("Fill all required fields");
    await api.post("/leaves", { ...form, days: calcDays(form.fromDate, form.toDate) });
    toast.success("Leave applied");
    setOpen(false);
    setForm({ employeeId: "", employeeName: "", leaveType: "CL", fromDate: "", toDate: "", days: 1, reason: "" });
    load();
  };

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
      <PageHeader testId="leaves-page" title="Leave Management" subtitle="Apply, approve or reject employee leave requests"
        actions={<button onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white"><Plus size={14} /> Apply Leave</button>}
      />
      {(!loading && rows.length === 0) ? <EmptyState icon={CalendarClock} title="No leave requests" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="leaves-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle>Apply Leave</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Employee*</label>
              <select onChange={(e) => pickEmp(e.target.value)} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                <option value="">Select employee…</option>
                {emps.map(e => <option key={e.id} value={e.id}>{e.name} ({e.employeeId})</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Leave Type</label>
              <select value={form.leaveType} onChange={(e) => setForm({...form, leaveType: e.target.value})} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px] bg-white">
                {LEAVE_TYPES.map(t => <option key={t} value={t}>{t === "CL" ? "CL - Casual Leave" : t === "EL" ? "EL - Earned Leave" : t === "ML" ? "ML - Medical Leave" : t === "PL" ? "PL - Privileged Leave" : t === "LWP" ? "LWP - Leave Without Pay" : "OD - On Duty"}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-500 mb-1 block">From Date*</label>
                <input type="date" value={form.fromDate} onChange={(e) => setForm({...form, fromDate: e.target.value})} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px]" />
              </div>
              <div>
                <label className="text-[11px] text-slate-500 mb-1 block">To Date*</label>
                <input type="date" value={form.toDate} onChange={(e) => setForm({...form, toDate: e.target.value})} className="w-full h-9 px-2 rounded-lg border border-slate-200 text-[12.5px]" />
              </div>
            </div>
            {form.fromDate && form.toDate && <div className="text-[12px] text-slate-600 bg-slate-50 px-3 py-2 rounded-lg">Total days: <strong>{calcDays(form.fromDate, form.toDate)}</strong></div>}
            <div>
              <label className="text-[11px] text-slate-500 mb-1 block">Reason</label>
              <textarea value={form.reason} onChange={(e) => setForm({...form, reason: e.target.value})} rows={2} className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[12.5px] resize-none" />
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button onClick={save} className="px-4 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Apply</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
