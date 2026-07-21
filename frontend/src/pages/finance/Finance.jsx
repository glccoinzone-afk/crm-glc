import React, { useEffect, useState } from "react";
import { BarChart3, ScrollText, FileText, Wallet } from "lucide-react";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState, StatCard } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/pages/crm/Leads";
import { toast } from "sonner";

export function ChartOfAccounts() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get("/accounts").then((r) => { setRows(r.data.items || []); }).finally(() => setLoading(false)); }, []);
  const columns = [
    { key: "code", header: "Code", mono: true },
    { key: "name", header: "Account", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "type", header: "Type", render: (r) => <span className="text-[11px] uppercase tracking-wide text-slate-500">{r.type}</span> },
    { key: "balance", header: "Balance", mono: true, align: "right", render: (r) => fmtInr(r.balance) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="coa-page" title="Chart of Accounts" subtitle="Indian standard COA — assets, liabilities, equity, income, expenses" />
      <DataGrid columns={columns} rows={rows} loading={loading} testId="coa-grid" />
    </div>
  );
}

export function Journal() {
  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), narration: "", entries: [{ accountId: "", debit: 0, credit: 0 }, { accountId: "", debit: 0, credit: 0 }] });
  const load = () => api.get("/journal").then((r) => setRows(r.data.items || []));
  useEffect(() => { load(); api.get("/accounts").then((r) => setAccounts(r.data.items || [])); }, []);
  const setEntry = (i, k, v) => { const es = [...form.entries]; es[i][k] = k === "accountId" ? v : Number(v); setForm({ ...form, entries: es }); };
  const save = async () => {
    try { await api.post("/journal", form); toast.success("Journal entry created"); setOpen(false); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const columns = [
    { key: "date", header: "Date" },
    { key: "narration", header: "Narration" },
    { key: "totalDebit", header: "Debit", mono: true, align: "right", render: (r) => fmtInr(r.totalDebit) },
    { key: "totalCredit", header: "Credit", mono: true, align: "right", render: (r) => fmtInr(r.totalCredit) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="journal-page" title="General Journal" subtitle="Double-entry bookkeeping journal entries" actions={
        <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          + New Entry
        </button>
      }/>
      <DataGrid columns={columns} rows={rows} testId="journal-grid" empty="No entries yet." />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Journal Entry</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date" v={form.date} on={(v) => setForm({ ...form, date: v })} type="date" />
              <Field label="Narration" v={form.narration} on={(v) => setForm({ ...form, narration: v })} />
            </div>
            {form.entries.map((e, i) => (
              <div key={i} className="grid grid-cols-3 gap-2">
                <select value={e.accountId} onChange={(x) => setEntry(i, "accountId", x.target.value)} className="h-9 px-2 rounded-md border border-slate-200 text-[12.5px] bg-white">
                  <option value="">Select account</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
                </select>
                <input type="number" placeholder="Debit" value={e.debit} onChange={(x) => setEntry(i, "debit", x.target.value)} className="h-9 px-2 rounded-md border border-slate-200 text-right font-mono text-[12.5px]" />
                <input type="number" placeholder="Credit" value={e.credit} onChange={(x) => setEntry(i, "credit", x.target.value)} className="h-9 px-2 rounded-md border border-slate-200 text-right font-mono text-[12.5px]" />
              </div>
            ))}
            <button onClick={() => setForm({ ...form, entries: [...form.entries, { accountId: "", debit: 0, credit: 0 }] })} className="text-[12px] text-[hsl(var(--primary))]">+ Add line</button>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Save Entry</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function GstReports() {
  const [data, setData] = useState(null);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  useEffect(() => { api.get("/reports/gst", { params: { month } }).then((r) => setData(r.data)); }, [month]);
  const s = data?.summary || {};
  const columns = [
    { key: "invoiceNo", header: "Invoice", mono: true },
    { key: "customerName", header: "Customer" },
    { key: "customerGst", header: "GSTIN", mono: true },
    { key: "subtotal", header: "Taxable", mono: true, align: "right", render: (r) => fmtInr(r.subtotal) },
    { key: "cgst", header: "CGST", mono: true, align: "right", render: (r) => fmtInr(r.cgst) },
    { key: "sgst", header: "SGST", mono: true, align: "right", render: (r) => fmtInr(r.sgst) },
    { key: "igst", header: "IGST", mono: true, align: "right", render: (r) => fmtInr(r.igst) },
    { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="gst-page" title="GST Reports (GSTR-1 / 3B)" subtitle="Filing-ready outward supplies breakdown" actions={
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white" />
      }/>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Invoices" value={s.count || 0} icon={FileText} tone="primary" />
        <StatCard label="Taxable Value" value={fmtInr(s.taxableValue)} icon={BarChart3} tone="accent" />
        <StatCard label="CGST" value={fmtInr(s.cgst)} icon={ScrollText} tone="warn" />
        <StatCard label="SGST" value={fmtInr(s.sgst)} icon={ScrollText} tone="warn" />
        <StatCard label="Total Tax" value={fmtInr((s.cgst||0)+(s.sgst||0)+(s.igst||0))} icon={Wallet} tone="success" />
      </div>
      <DataGrid columns={columns} rows={data?.invoices || []} testId="gst-grid" empty="No invoices for this month." />
    </div>
  );
}

export function Expenses() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", amount: 0, category: "Travel" });
  const load = () => { setLoading(true); api.get("/expenses").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);
  const save = async () => { await api.post("/expenses", form); toast.success("Expense submitted"); setOpen(false); load(); };
  const act = async (r, status) => { await api.put(`/expenses/${r.id}`, { status }); toast.success(status); load(); };

  const columns = [
    { key: "title", header: "Title" },
    { key: "category", header: "Category" },
    { key: "amount", header: "Amount", mono: true, align: "right", render: (r) => fmtInr(r.amount) },
    { key: "submittedBy", header: "By" },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "actions", header: "", align: "right", render: (r) => r.status === "PENDING" ? (
        <div className="flex gap-1 justify-end">
          <button onClick={() => act(r, "APPROVED")} className="text-[11.5px] text-emerald-600 hover:underline">Approve</button>
          <span className="text-slate-300">·</span>
          <button onClick={() => act(r, "REJECTED")} className="text-[11.5px] text-rose-600 hover:underline">Reject</button>
        </div>
      ) : <span className="text-[11px] text-slate-400">—</span>
    },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="expenses-page" title="Expenses" subtitle="Employee expense claims & approvals" actions={
        <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">+ New Expense</button>
      }/>
      <DataGrid columns={columns} rows={rows} loading={loading} testId="expenses-grid" />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle>New Expense</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Title*" v={form.title} on={(v) => setForm({ ...form, title: v })} />
            <Field label="Amount ₹" v={form.amount} on={(v) => setForm({ ...form, amount: Number(v) })} type="number" />
            <SelectField label="Category" v={form.category} on={(v) => setForm({ ...form, category: v })} opts={["Travel", "Meals", "Office", "Software", "Other"]} />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Submit</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
