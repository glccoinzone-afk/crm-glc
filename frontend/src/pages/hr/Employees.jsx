import React, { useEffect, useState } from "react";
import { Plus, UserRound } from "lucide-react";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/pages/crm/Leads";
import { toast } from "sonner";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function Employees() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", department: "", designation: "", salary: 0 });

  const load = () => { setLoading(true); api.get("/employees", { params: q ? { q } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, [q]);

  const save = async () => { await api.post("/employees", form); toast.success("Employee added"); setOpen(false); load(); };

  const columns = [
    { key: "name", header: "Employee", render: (r) => {
        const initials = (r.name || "").split(" ").map((s) => s[0]).join("").slice(0, 2);
        return (
          <div className="flex items-center gap-2.5">
            <Avatar className="w-8 h-8"><AvatarImage src={r.avatar} /><AvatarFallback className="bg-[hsl(var(--primary))] text-white text-[11px]">{initials}</AvatarFallback></Avatar>
            <div>
              <div className="font-medium text-slate-900">{r.name}</div>
              <div className="text-[11.5px] text-slate-500 font-mono">{r.employeeId}</div>
            </div>
          </div>
        );
      }
    },
    { key: "email", header: "Email" },
    { key: "department", header: "Department" },
    { key: "designation", header: "Role" },
    { key: "salary", header: "Salary", mono: true, align: "right", render: (r) => fmtInr(r.salary) },
    { key: "status", header: "Status", render: (r) => <span className="text-[11.5px] font-medium text-emerald-600">{r.status}</span> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="employees-page" title="Employees" subtitle="Central HR directory across departments and verticals" actions={
        <button data-testid="new-employee-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          <Plus size={14} /> New Employee
        </button>
      }/>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search employees…" className="w-full max-w-sm h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px]" />
      {(!loading && rows.length === 0) ? <EmptyState icon={UserRound} title="No employees yet" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="employees-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Employee</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="emp-name" />
            <Field label="Email*" v={form.email} on={(v) => setForm({ ...form, email: v })} />
            <Field label="Phone" v={form.phone} on={(v) => setForm({ ...form, phone: v })} />
            <Field label="Department" v={form.department} on={(v) => setForm({ ...form, department: v })} />
            <Field label="Designation" v={form.designation} on={(v) => setForm({ ...form, designation: v })} />
            <Field label="Salary ₹" v={form.salary} on={(v) => setForm({ ...form, salary: Number(v) })} type="number" />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-employee" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Create</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
