import React, { useEffect, useMemo, useState } from "react";
import { Building2, CheckCircle2, Clock, FileQuestion, ShoppingCart, IndianRupee, Phone, MessageCircle, RefreshCw, Search } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatCard, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { toast } from "sonner";

const TABS = [["", "All"], ["pending", "Waiting"], ["approved", "Approved"], ["rejected", "Rejected"]];
const TYPES = { restaurant: "Restaurant", hotel: "Hotel", mess: "Mess / Canteen", caterer: "Caterer", retailer: "Retailer", other: "Other" };
const digits = (p) => String(p || "").replace(/\D/g, "").slice(-10);

export default function BusinessAccounts() {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [tab, setTab] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  const load = () => {
    setLoading(true);
    api.get("/business-accounts", { params: { ...(tab ? { status: tab } : {}), ...(q ? { q } : {}) } })
      .then((r) => { setRows(r.data.items || []); setSummary(r.data.summary || {}); })
      .catch(() => toast.error("Could not load the business accounts"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [tab]);   // eslint-disable-line react-hooks/exhaustive-deps

  const cols = useMemo(() => [
    { key: "name", header: "Business", render: (r) => (
      <div><div className="font-medium text-slate-900">{r.name}</div>
        <div className="text-[11px] text-slate-500">{TYPES[r.type] || r.type}{r.gst ? ` · GST ${r.gst}` : ""}{r.code ? ` · ${r.code}` : ""}</div></div>) },
    { key: "contact", header: "Contact", render: (r) => (
      <div><div>{r.contact || "—"}</div><div className="text-[11px] text-slate-500">{r.phone || ""}{r.city ? ` · ${r.city}` : ""}</div></div>) },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={(r.status || "").toUpperCase()} /> },
    { key: "orders", header: "Orders", align: "right", mono: true },
    { key: "spend", header: "Bought", align: "right", mono: true, render: (r) => fmtInr(r.spend || 0) },
    { key: "saved", header: "Saved", align: "right", mono: true, render: (r) => fmtInr(r.saved || 0) },
    { key: "lastOrderAt", header: "Last order", render: (r) => (r.lastOrderAt ? fmtDate(r.lastOrderAt) : "—") },
    { key: "quotesOpen", header: "Rate requests", align: "right", render: (r) => (r.quotesOpen ? <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[11px] font-medium">{r.quotesOpen} open</span> : <span className="text-slate-400">{r.quotesTotal || 0}</span>) },
    { key: "registeredAt", header: "Joined", render: (r) => fmtDate(r.registeredAt || r.createdAt) },
    { key: "actions", header: "", sort: false, align: "right", render: (r) => (
      <div className="flex items-center gap-1 justify-end" onClick={(e) => e.stopPropagation()}>
        {digits(r.phone).length === 10 && <a href={`tel:+91${digits(r.phone)}`} className="p-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50" title="Call"><Phone size={13} /></a>}
        {digits(r.phone).length === 10 && <a href={`https://wa.me/91${digits(r.phone)}`} target="_blank" rel="noreferrer" className="p-1.5 rounded-md border border-emerald-200 text-emerald-600 hover:bg-emerald-50" title="WhatsApp"><MessageCircle size={13} /></a>}
      </div>) },
  ], []);

  return (
    <div data-testid="business-accounts-page">
      <PageHeader testId="business-header" title="GLC Business" subtitle="Restaurants, hotels and messes that buy in bulk on the GLC Business page: who they are, what they bought and what they asked for."
        actions={<button onClick={load} className="inline-flex items-center gap-1.5 text-[12.5px] px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"><RefreshCw size={13} /> Refresh</button>} />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <StatCard label="Accounts" value={summary.total ?? 0} icon={Building2} tone="primary" />
        <StatCard label="Approved" value={summary.approved ?? 0} icon={CheckCircle2} tone="success" />
        <StatCard label="Waiting" value={summary.pending ?? 0} icon={Clock} tone="warn" />
        <StatCard label="Rate requests open" value={summary.quotesOpen ?? 0} icon={FileQuestion} tone="accent" />
        <StatCard label="Bulk orders" value={summary.orders ?? 0} icon={ShoppingCart} tone="slate" />
        <StatCard label="Bought" value={fmtInr(summary.spend || 0)} icon={IndianRupee} tone="primary" />
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        {TABS.map(([k, label]) => (
          <button key={k || "all"} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-full text-[12.5px] border ${tab === k ? "bg-[hsl(var(--primary))] text-white border-transparent" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>{label}</button>
        ))}
        <form className="ml-auto flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); load(); }}>
          <div className="relative"><Search size={13} className="absolute left-2.5 top-2.5 text-slate-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, phone, city, GST..." className="pl-7 pr-3 py-1.5 text-[12.5px] rounded-lg border border-slate-200 w-64" /></div>
          <button className="px-3 py-1.5 text-[12.5px] rounded-lg bg-slate-900 text-white">Search</button>
        </form>
      </div>

      {!loading && rows.length === 0 ? (
        <EmptyState title="No business accounts yet" description="They appear here as soon as a restaurant, hotel or mess registers on the GLC Business page." icon={Building2} />
      ) : (
        <DataGrid columns={cols} rows={rows} loading={loading} testId="business-grid" exportName="glc-business-accounts" onRowClick={(r) => setOpen(open?.id === r.id ? null : r)} />
      )}

      {open && (
        <div className="mt-4 bg-white rounded-2xl border border-slate-200/70 p-5 card-elev" data-testid="business-detail">
          <div className="flex items-start justify-between">
            <div><div className="text-[15px] font-semibold">{open.name}</div>
              <div className="text-[12px] text-slate-500">{TYPES[open.type] || open.type}{open.city ? ` · ${open.city}` : ""}{open.gst ? ` · GST ${open.gst}` : ""}</div></div>
            <button className="text-[12px] text-slate-500" onClick={() => setOpen(null)}>Close</button>
          </div>
          <div className="grid md:grid-cols-3 gap-4 mt-4 text-[12.5px]">
            <div><div className="text-slate-500 text-[11px] uppercase tracking-wide mb-1">Contact</div>{open.contact || "—"}<br />{open.phone || "—"}<br />{open.email || "—"}</div>
            <div><div className="text-slate-500 text-[11px] uppercase tracking-wide mb-1">Their note</div>{open.notes || "—"}{open.adminNote && <div className="mt-2 text-slate-500">Admin note: {open.adminNote}</div>}</div>
            <div><div className="text-slate-500 text-[11px] uppercase tracking-wide mb-1">Latest rate request</div>{open.lastQuote ? (<><div>{open.lastQuote.items}</div><div className="text-slate-500 mt-1">{open.lastQuote.needed_by ? `Needed by ${open.lastQuote.needed_by} · ` : ""}{open.lastQuote.status}</div></>) : "—"}</div>
          </div>
          <div className="mt-4"><div className="text-slate-500 text-[11px] uppercase tracking-wide mb-1">History</div>
            <ul className="text-[12px] text-slate-600 space-y-1">{(open.activities || []).slice().reverse().map((a) => <li key={a.id}>{fmtDate(a.at)} — {a.text}</li>)}</ul></div>
        </div>
      )}
    </div>
  );
}
