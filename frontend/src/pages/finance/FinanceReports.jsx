import React, { useEffect, useRef, useState } from "react";
import { Scale, FileText, Clock, Receipt, Printer, CheckCircle2, AlertTriangle, Wallet } from "lucide-react";
import { useReactToPrint } from "react-to-print";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatCard } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useCompany } from "@/hooks/useCompany";
import { toast } from "sonner";

const PrintBtn = ({ onClick, tid }) => (
  <button data-testid={tid} onClick={onClick} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
    <Printer size={13} /> Print / PDF
  </button>
);

const errText = (e) => e?.response?.data?.detail || "Could not load (check that your role has finance access)";
const money = (k) => ({ key: k, header: k.toUpperCase(), mono: true, align: "right", render: (r) => fmtInr(r[k]) });

function Section({ title, hint, children }) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h3 className="text-[13.5px] font-semibold text-slate-800">{title}</h3>
        {hint && <span className="text-[11.5px] text-slate-500">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- Trial balance + ledger
export function TrialBalance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ledger, setLedger] = useState(null);
  const ref = useRef(null);
  const print = useReactToPrint({ contentRef: ref, documentTitle: "Trial-Balance" });
  const company = useCompany();
  useEffect(() => {
    api.get("/finance/trial-balance").then((r) => setData(r.data)).catch((e) => toast.error(errText(e))).finally(() => setLoading(false));
  }, []);
  const openLedger = (r) => api.get(`/finance/ledger/${r.code}`).then((x) => setLedger(x.data)).catch((e) => toast.error(errText(e)));
  const columns = [
    { key: "code", header: "Code", mono: true },
    { key: "name", header: "Account", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "type", header: "Type", render: (r) => <span className="text-[11px] uppercase tracking-wide text-slate-500">{r.type}</span> },
    { key: "debit", header: "Debit", mono: true, align: "right", render: (r) => fmtInr(r.debit) },
    { key: "credit", header: "Credit", mono: true, align: "right", render: (r) => fmtInr(r.credit) },
    { key: "balance", header: "Balance", mono: true, align: "right", render: (r) => fmtInr(r.balance) },
  ];
  const rows = (data?.rows || []).filter((r) => r.debit || r.credit);
  return (
    <div className="space-y-6">
      <PageHeader testId="tb-page" title="Trial Balance" subtitle="Every account's debit and credit totals. Click an account for its ledger." actions={<PrintBtn onClick={print} tid="tb-print" />} />
      <div ref={ref} className="space-y-4">
        <div className="hidden print:block px-2 pb-2">
          <div className="text-[18px] font-semibold">{company?.legalName || "GLC Zone Private Limited"} — Trial Balance</div>
          <div className="text-[12px] text-slate-500">GSTIN {company?.gstin} · {company?.state} · FY {company?.financialYear}</div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard label="Total Debit" value={fmtInr(data?.totalDebit)} icon={Scale} tone="primary" />
          <StatCard label="Total Credit" value={fmtInr(data?.totalCredit)} icon={Scale} tone="accent" />
          <StatCard label="Books" value={data ? (data.balanced ? "Balanced" : "NOT BALANCED") : "…"} icon={data?.balanced === false ? AlertTriangle : CheckCircle2} tone={data?.balanced === false ? "danger" : "success"} />
        </div>
        <DataGrid columns={columns} rows={rows} loading={loading} testId="tb-grid" onRowClick={openLedger} empty="No entries posted yet." />
      </div>
      <Dialog open={!!ledger} onOpenChange={(o) => !o && setLedger(null)}>
        <DialogContent className="max-w-3xl rounded-2xl">
          <DialogHeader><DialogTitle>{ledger?.account?.code} · {ledger?.account?.name} — Ledger</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-auto">
            <DataGrid testId="ledger-grid" empty="No entries." rows={ledger?.entries || []} columns={[
              { key: "date", header: "Date", render: (r) => fmtDate(r.date) },
              { key: "narration", header: "Narration" },
              { key: "debit", header: "Debit", mono: true, align: "right", render: (r) => (r.debit ? fmtInr(r.debit) : "") },
              { key: "credit", header: "Credit", mono: true, align: "right", render: (r) => (r.credit ? fmtInr(r.credit) : "") },
              { key: "balance", header: "Balance", mono: true, align: "right", render: (r) => fmtInr(r.balance) },
            ]} />
          </div>
          <div className="text-right text-[13px] font-medium">Closing balance: <span className="font-mono">{fmtInr(ledger?.closing)}</span></div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------- GSTR-1 / GSTR-3B
const thisMonth = () => new Date().toISOString().slice(0, 7);

export function GstReturns() {
  const [tab, setTab] = useState("gstr1");
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const ref = useRef(null);
  const print = useReactToPrint({ contentRef: ref, documentTitle: `${tab.toUpperCase()}-${month}` });
  const company = useCompany();
  useEffect(() => {
    setLoading(true); setData(null);
    api.get(`/reports/${tab}`, { params: { month } }).then((r) => setData(r.data)).catch((e) => toast.error(errText(e))).finally(() => setLoading(false));
  }, [tab, month]);

  return (
    <div className="space-y-6">
      <PageHeader testId="gstr-page" title="GST Returns" subtitle="GSTR-1 and GSTR-3B style working, from invoices, credit notes and purchases. A draft for your accountant." actions={
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white" />
          <PrintBtn onClick={print} tid="gstr-print" />
        </div>
      } />
      <div className="inline-flex rounded-lg bg-slate-100 p-1 text-[12.5px]">
        {[["gstr1", "GSTR-1 (outward)"], ["gstr3b", "GSTR-3B (summary)"]].map(([k, l]) => (
          <button key={k} data-testid={`tab-${k}`} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-md font-medium ${tab === k ? "bg-white shadow text-slate-900" : "text-slate-600"}`}>{l}</button>
        ))}
      </div>
      <div ref={ref} className="space-y-6">
        <div className="hidden print:block px-2 pb-2">
          <div className="text-[18px] font-semibold">{tab === "gstr1" ? "GSTR-1 working" : "GSTR-3B working"} — {month}</div>
          <div className="text-[12px] text-slate-500">GSTIN {company?.gstin} · {company?.state}</div>
        </div>
        {loading && <div className="text-[13px] text-slate-500">Loading…</div>}
        {data && tab === "gstr1" && <Gstr1 d={data} />}
        {data && tab === "gstr3b" && <Gstr3b d={data} />}
      </div>
    </div>
  );
}

function Gstr1({ d }) {
  const t = d.totals || {};
  const docs = d.documents || {};
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Taxable value (net)" value={fmtInr(t.taxable)} icon={FileText} tone="primary" />
        <StatCard label="CGST" value={fmtInr(t.cgst)} icon={Receipt} tone="warn" />
        <StatCard label="SGST" value={fmtInr(t.sgst)} icon={Receipt} tone="warn" />
        <StatCard label="IGST" value={fmtInr(t.igst)} icon={Receipt} tone="warn" />
      </div>
      <div className="text-[12px] text-slate-500">
        Documents issued: {docs.invoices || 0} invoices{docs.from ? ` (${docs.from} to ${docs.to})` : ""}, {docs.cancelled || 0} cancelled, {docs.creditNotes || 0} credit notes. Totals are net of credit notes.
      </div>
      <Section title="B2B — to registered buyers" hint="invoice-wise">
        <DataGrid testId="g1-b2b" rows={d.b2b || []} empty="No B2B invoices." columns={[
          { key: "gstin", header: "Buyer GSTIN", mono: true }, { key: "invoiceNo", header: "Invoice", mono: true },
          { key: "date", header: "Date" }, { key: "pos", header: "Place of supply" },
          { key: "value", header: "Value", mono: true, align: "right", render: (r) => fmtInr(r.value) },
          { key: "taxable", header: "Taxable", mono: true, align: "right", render: (r) => fmtInr(r.taxable) },
          money("cgst"), money("sgst"), money("igst"),
        ]} />
      </Section>
      {(d.b2cl || []).length > 0 && (
        <Section title="B2C large — inter-state above ₹2.5 lakh">
          <DataGrid testId="g1-b2cl" rows={d.b2cl} columns={[
            { key: "invoiceNo", header: "Invoice", mono: true }, { key: "date", header: "Date" }, { key: "pos", header: "Place of supply" },
            { key: "value", header: "Value", mono: true, align: "right", render: (r) => fmtInr(r.value) }, money("igst"),
          ]} />
        </Section>
      )}
      <Section title="B2C small — state and rate wise">
        <DataGrid testId="g1-b2cs" rows={d.b2cs || []} empty="No B2C sales." columns={[
          { key: "pos", header: "Place of supply" }, { key: "rate", header: "Rate", render: (r) => `${r.rate}%` },
          { key: "taxable", header: "Taxable", mono: true, align: "right", render: (r) => fmtInr(r.taxable) }, money("cgst"), money("sgst"), money("igst"),
        ]} />
      </Section>
      <Section title="Credit notes">
        <DataGrid testId="g1-cdn" rows={d.cdn || []} empty="No credit notes." columns={[
          { key: "noteNo", header: "Note", mono: true }, { key: "date", header: "Date" }, { key: "invoiceNo", header: "Against", mono: true },
          { key: "type", header: "Buyer" }, { key: "value", header: "Value", mono: true, align: "right", render: (r) => fmtInr(r.value) },
          money("cgst"), money("sgst"), money("igst"),
        ]} />
      </Section>
      <Section title="HSN / SAC summary" hint="quantity net of returns">
        <DataGrid testId="g1-hsn" rows={d.hsn || []} empty="No lines." columns={[
          { key: "hsn", header: "HSN / SAC", mono: true }, { key: "rate", header: "Rate", render: (r) => `${r.rate}%` },
          { key: "qty", header: "Qty", mono: true, align: "right" },
          { key: "taxable", header: "Taxable", mono: true, align: "right", render: (r) => fmtInr(r.taxable) }, money("cgst"), money("sgst"), money("igst"),
        ]} />
      </Section>
    </>
  );
}

function Gstr3b({ d }) {
  const o = d.outward || {}, itc = d.itcAvailable || {}, pay = d.netPayableCash || {}, cf = d.itcCarriedForward || {};
  const rows = [
    { id: "cgst", head: "CGST", out: o.cgst, itc: itc.cgst, pay: pay.cgst },
    { id: "sgst", head: "SGST", out: o.sgst, itc: itc.sgst, pay: pay.sgst },
    { id: "igst", head: "IGST", out: o.igst, itc: itc.igst, pay: pay.igst },
  ];
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Taxable outward" value={fmtInr(o.taxableValue)} icon={FileText} tone="primary" />
        <StatCard label="Nil / exempt outward" value={fmtInr(o.nilRatedValue)} icon={FileText} tone="accent" />
        <StatCard label="Tax payable in cash" value={fmtInr(pay.total)} icon={Wallet} tone="warn" />
        <StatCard label="ITC carried forward" value={fmtInr(cf.total)} icon={Clock} tone="success" />
      </div>
      <Section title="Tax liability and input credit" hint={`ITC from ${d.itcDocuments || 0} received purchase(s) with a valid supplier GSTIN`}>
        <DataGrid testId="g3b-grid" rows={rows} columns={[
          { key: "head", header: "Head" },
          { key: "out", header: "Output tax", mono: true, align: "right", render: (r) => fmtInr(r.out) },
          { key: "itc", header: "ITC available", mono: true, align: "right", render: (r) => fmtInr(r.itc) },
          { key: "pay", header: "Payable in cash", mono: true, align: "right", render: (r) => fmtInr(r.pay) },
        ]} />
      </Section>
      {d.note && <div className="text-[12px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">{d.note}</div>}
    </>
  );
}

// ---------------------------------------------------------------- Receivables ageing
export function ReceivablesAgeing() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get("/finance/receivables-ageing").then((r) => setData(r.data)).catch((e) => toast.error(errText(e))).finally(() => setLoading(false)); }, []);
  const labels = { notDue: "Not due", "1-30": "1–30 days", "31-60": "31–60 days", "61-90": "61–90 days", "90+": "90+ days" };
  const t = data?.totals || {};
  const columns = [{ key: "customer", header: "Customer", render: (r) => <span className="font-medium">{r.customer}</span> },
    ...(data?.buckets || []).map((b) => ({ key: b, header: labels[b], mono: true, align: "right", render: (r) => (r[b] ? fmtInr(r[b]) : "—") })),
    { key: "total", header: "Total due", mono: true, align: "right", render: (r) => <b>{fmtInr(r.total)}</b> }];
  return (
    <div className="space-y-6">
      <PageHeader testId="ageing-page" title="Receivables Ageing" subtitle="Unpaid invoice balances by how overdue they are" />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {(data?.buckets || []).map((b) => <StatCard key={b} label={labels[b]} value={fmtInr(t[b])} icon={Clock} tone={b === "90+" ? "danger" : b === "notDue" ? "success" : "warn"} />)}
      </div>
      <DataGrid columns={columns} rows={data?.rows || []} loading={loading} testId="ageing-grid" empty="No unpaid invoices." />
    </div>
  );
}

// ---------------------------------------------------------------- Credit notes list
export function CreditNotes() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState(null);
  useEffect(() => { api.get("/credit-notes").then((r) => setRows(r.data.items || [])).catch((e) => toast.error(errText(e))).finally(() => setLoading(false)); }, []);
  return (
    <div className="space-y-6">
      <PageHeader testId="cn-page" title="Credit Notes" subtitle="Returns and corrections against invoices. Create one from the Invoices page." />
      <DataGrid testId="cn-grid" columns={[
        { key: "noteNo", header: "Note", mono: true, render: (r) => <span className="font-medium">{r.noteNo}</span> },
        { key: "noteDate", header: "Date", render: (r) => fmtDate(r.noteDate) },
        { key: "invoiceNo", header: "Against", mono: true },
        { key: "customerName", header: "Customer" },
        { key: "reason", header: "Reason" },
        { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
      ]} rows={rows} loading={loading} onRowClick={setView} empty="No credit notes yet." />
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader><DialogTitle>{view?.noteNo} against {view?.invoiceNo}</DialogTitle></DialogHeader>
          <DataGrid testId="cn-lines" rows={view?.lines || []} columns={[
            { key: "name", header: "Item" }, { key: "hsn", header: "HSN", mono: true },
            { key: "qty", header: "Qty", mono: true, align: "right" }, { key: "gstRate", header: "GST", render: (r) => `${r.gstRate}%` },
            { key: "taxable", header: "Taxable", mono: true, align: "right", render: (r) => fmtInr(r.taxable) },
            { key: "total", header: "Total", mono: true, align: "right", render: (r) => fmtInr(r.total) },
          ]} />
          <div className="text-right text-[13px] font-semibold">Total credited: <span className="font-mono">{fmtInr(view?.total)}</span></div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
