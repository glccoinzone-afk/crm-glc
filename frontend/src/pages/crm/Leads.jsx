import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Search, UserSquare2, Trash2, ArrowRight, Phone, MessageCircle, CalendarClock } from "lucide-react";
import api, { fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState, Pager, ErrorBanner } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const SOURCES = ["MANUAL", "WEBSITE", "WHATSAPP", "REFERRAL", "CAMPAIGN", "SOCIAL", "COLD_CALL"];
const STATUSES = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];
const CALL_RESULTS = ["", "Answered: interested", "Answered: not interested", "Answered: call me later", "No answer", "Busy", "Wrong number"];
const DELETE_ROLES = ["Super Admin", "Admin", "Manager"];
const LIMIT = 50;

const empty = { name: "", email: "", phone: "", company: "", source: "MANUAL", status: "NEW", score: 40, value: 0, notes: "", tags: [], assignedTo: "", followUpDate: "" };

// Indian dates: the CRM is used in India, so "today" is Indian today
const todayStr = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const prettyDay = (d) => { try { return new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" }); } catch { return d; } };
const waLink = (phone, name) => {
  const d = (phone || "").replace(/\D/g, "").slice(-10);
  if (d.length !== 10) return null;
  const msg = `Hello ${name || ""}, this is the GLC Zone team. `;
  return `https://wa.me/91${d}?text=${encodeURIComponent(msg)}`;
};
const telLink = (phone) => {
  const d = (phone || "").replace(/\D/g, "").slice(-10);
  return d.length === 10 ? `tel:+91${d}` : null;
};
const errText = (e, fallback) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && d.message) return d.message;
  return fallback;
};

function FollowCell({ r }) {
  const d = (r.followUpDate || "").slice(0, 10);
  if (!d) return <span className="text-slate-400">—</span>;
  const t = todayStr();
  const closed = r.status === "WON" || r.status === "LOST";
  if (!closed && d < t) return <span className="inline-flex items-center gap-1 text-rose-700 font-medium text-[12px]"><CalendarClock size={13} />Overdue · {prettyDay(d)}</span>;
  if (!closed && d === t) return <span className="inline-flex items-center gap-1 text-amber-700 font-medium text-[12px]"><CalendarClock size={13} />Today</span>;
  return <span className="text-slate-600 text-[12px]">{prettyDay(d)}</span>;
}

export default function Leads() {
  const { user } = useAuth() || {};
  const canDelete = DELETE_ROLES.includes(user?.role);
  const initial = new URLSearchParams(window.location.search);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [view, setView] = useState(initial.get("follow") === "due" ? "due" : initial.get("assigned") === "me" ? "mine" : "all");
  const [summary, setSummary] = useState({});
  const [agents, setAgents] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [dup, setDup] = useState(null);
  const [selId, setSelId] = useState(null);

  const params = useMemo(() => {
    const p = { page, limit: LIMIT };
    if (q) p.q = q;
    if (status) p.status = status;
    if (source) p.source = source;
    if (view === "today") p.follow = "today";
    if (view === "overdue") p.follow = "overdue";
    if (view === "due") { p.follow = "due"; p.assigned = "me"; }
    if (view === "mine") p.assigned = "me";
    if (view === "unassigned") p.assigned = "none";
    return p;
  }, [page, q, status, source, view]);

  const load = useCallback(() => {
    setLoading(true); setError("");
    api.get("/leads", { params })
      .then((r) => { setRows(r.data.items || []); setTotal(r.data.total || 0); })
      .catch((e) => setError(errText(e, "Could not load the leads. Please try again.")))
      .finally(() => setLoading(false));
    api.get("/leads/summary").then((r) => setSummary(r.data || {})).catch(() => {});
  }, [params]);

  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, q]);
  useEffect(() => { api.get("/ocm/agents").then((r) => setAgents(r.data.items || [])).catch(() => {}); }, []);
  useEffect(() => { setPage(1); }, [q, status, source, view]);

  const save = async (force = false) => {
    setSaving(true);
    try {
      const body = { ...form, assignedTo: form.assignedTo || null, followUpDate: form.followUpDate || null };
      await api.post("/leads", body, { params: force ? { force: true } : {} });
      toast.success("Lead created");
      setOpen(false); setForm(empty); setDup(null);
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (e?.response?.status === 409 && d?.code === "duplicate") setDup(d);
      else toast.error(errText(e, "Could not save the lead"));
    }
    setSaving(false);
  };

  const convert = async (r) => {
    if (!window.confirm(`Convert "${r.name}" to a customer?`)) return;
    try { await api.post(`/leads/${r.id}/convert`); toast.success(`${r.name} is now a customer`); load(); }
    catch (e) { toast.error(errText(e, "Convert failed")); }
  };
  const del = async (r) => {
    if (!window.confirm(`Delete lead "${r.name}"? This cannot be undone.`)) return;
    try { await api.delete(`/leads/${r.id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(errText(e, "Delete failed")); }
  };

  const chips = [
    ["all", "All open", summary.open],
    ["today", "Due today", summary.today],
    ["overdue", "Overdue", summary.overdue, "danger"],
    ["mine", "Mine", summary.mine],
    ["unassigned", "Unassigned", summary.unassigned],
  ];

  const columns = [
    { key: "name", header: "Lead", render: (r) => (
        <div>
          <div className="font-medium text-slate-900">{r.name}</div>
          <div className="text-[11.5px] text-slate-500">{r.company || "—"}</div>
        </div>
      )
    },
    { key: "contact", header: "Contact", render: (r) => (
        <div>
          <div className="flex items-center gap-1.5 text-slate-800 text-[12.5px]">
            <span>{r.phone || "—"}</span>
            {telLink(r.phone) && <a href={telLink(r.phone)} onClick={(e) => e.stopPropagation()} title="Call" aria-label={`Call ${r.name}`} className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-emerald-700"><Phone size={13} /></a>}
            {waLink(r.phone, r.name) && <a href={waLink(r.phone, r.name)} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} title="WhatsApp" aria-label={`WhatsApp ${r.name}`} className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-emerald-700"><MessageCircle size={13} /></a>}
          </div>
          <div className="text-slate-500 text-[11.5px]">{r.email || ""}</div>
        </div>
      )
    },
    { key: "source", header: "Source", render: (r) => <span className="text-[11.5px] text-slate-600 uppercase tracking-wide">{r.source}</span> },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "follow", header: "Follow-up", render: (r) => <FollowCell r={r} /> },
    { key: "owner", header: "Owner", render: (r) => <span className="text-[12px] text-slate-700">{r.assignedName || <span className="text-slate-400">Unassigned</span>}</span> },
    { key: "value", header: "Deal value", mono: true, align: "right", render: (r) => fmtInr(r.value) },
    { key: "actions", header: "", align: "right", render: (r) => (
        <div className="flex items-center gap-1 justify-end">
          <button data-testid={`lead-convert-${r.id}`} onClick={(e) => { e.stopPropagation(); convert(r); }} title="Convert to customer" aria-label={`Convert ${r.name}`} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-emerald-600">
            <ArrowRight size={14} />
          </button>
          {canDelete && (
            <button data-testid={`lead-delete-${r.id}`} onClick={(e) => { e.stopPropagation(); del(r); }} title="Delete" aria-label={`Delete ${r.name}`} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-rose-600">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      )
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        testId="leads-page"
        title="Leads"
        subtitle="Call the right people at the right time: today's follow-ups come first"
        actions={
          <button data-testid="new-lead-btn" onClick={() => { setDup(null); setOpen(true); }} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Plus size={14} /> New Lead
          </button>
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        {chips.map(([key, label, n, tone]) => (
          <button key={key} onClick={() => setView(key)} className={`px-3 h-9 rounded-full text-[12.5px] border transition-colors ${view === key ? "bg-[hsl(var(--primary))] text-white border-transparent" : tone === "danger" && n > 0 ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"}`}>
            {label}{n !== undefined ? ` (${n})` : ""}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input data-testid="lead-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, phone, email…" className="w-full h-10 pl-9 pr-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
        </div>
        <select data-testid="lead-status-filter" value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)} className="h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px] outline-none">
          <option value="">All sources</option>
          {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error ? <ErrorBanner message={error} onRetry={load} /> : (!loading && rows.length === 0) ? (
        <EmptyState icon={UserSquare2} title={view === "all" && !q && !status && !source ? "No leads yet" : "No leads match this view"} description={view === "all" && !q && !status && !source ? "Start adding leads to build your sales pipeline." : "Try another tab or clear the filters."} action={
          <button onClick={() => { setView("all"); setQ(""); setStatus(""); setSource(""); }} className="px-3 py-2 rounded-lg bg-white border border-slate-200 text-[13px]">Show all leads</button>
        }/>
      ) : (
        <DataGrid columns={columns} rows={rows} loading={loading} testId="leads-grid" onRowClick={(r) => setSelId(r.id)} />
      )}
      <Pager page={page} total={total} limit={LIMIT} onPage={setPage} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="new-lead-dialog" className="max-w-lg rounded-2xl">
          <DialogHeader>
            <DialogTitle>New Lead</DialogTitle>
          </DialogHeader>
          {dup && (
            <div className="rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[12.5px] p-3">
              <div className="font-medium">{dup.message}</div>
              <div className="mt-1">Open the existing record instead, or create this one anyway.</div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="lead-name" />
            <Field label="Company" v={form.company} on={(v) => setForm({ ...form, company: v })} tid="lead-company" />
            <Field label="Email" v={form.email} on={(v) => setForm({ ...form, email: v })} tid="lead-email" />
            <Field label="Phone" v={form.phone} on={(v) => setForm({ ...form, phone: v })} tid="lead-phone" />
            <SelectField label="Source" v={form.source} on={(v) => setForm({ ...form, source: v })} opts={SOURCES} />
            <SelectField label="Status" v={form.status} on={(v) => setForm({ ...form, status: v })} opts={STATUSES} />
            <label className="text-[11.5px] font-medium text-slate-600">Owner
              <select value={form.assignedTo} onChange={(e) => setForm({ ...form, assignedTo: e.target.value })} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white outline-none focus:border-[hsl(var(--primary))]">
                <option value="">Nobody yet</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </label>
            <Field label="Next follow-up" v={form.followUpDate} on={(v) => setForm({ ...form, followUpDate: v })} type="date" />
            <Field label="Deal Value ₹" v={form.value} on={(v) => setForm({ ...form, value: Number(v) })} type="number" />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            {dup && <button onClick={() => { setOpen(false); if (dup.existing?.type === "lead") setSelId(dup.existing.id); else window.location.assign(`/crm/crm/customers/${dup.existing.id}`); }} className="px-3 py-2 rounded-lg border border-slate-200 text-[13px]">Open existing</button>}
            <button data-testid="save-lead" onClick={() => save(!!dup)} disabled={saving || !form.name} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] disabled:opacity-60">
              {saving ? "Saving…" : dup ? "Create anyway" : "Create Lead"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <LeadDetail id={selId} agents={agents} onClose={() => setSelId(null)} onChanged={load} />
    </div>
  );
}

function LeadDetail({ id, agents, onClose, onChanged }) {
  const [lead, setLead] = useState(null);
  const [edit, setEdit] = useState({});
  const [saving, setSaving] = useState(false);
  const [log, setLog] = useState({ type: "call", outcome: "", text: "", nextFollowUp: "" });
  const [err, setErr] = useState("");

  const fetchLead = useCallback(() => {
    if (!id) return;
    setErr("");
    api.get(`/leads/${id}`).then((r) => { setLead(r.data); setEdit({}); }).catch((e) => setErr(errText(e, "Could not open this lead")));
  }, [id]);
  useEffect(() => { setLead(null); setLog({ type: "call", outcome: "", text: "", nextFollowUp: "" }); fetchLead(); }, [fetchLead]);

  const val = (k) => (k in edit ? edit[k] : lead?.[k]) ?? "";
  const changed = Object.keys(edit).length > 0;
  const saveEdit = async () => {
    setSaving(true); setErr("");
    try {
      const body = { ...edit };
      if ("assignedTo" in body && !body.assignedTo) body.assignedTo = null;
      const r = await api.patch(`/leads/${id}`, body);
      setLead(r.data); setEdit({}); toast.success("Saved"); onChanged();
    } catch (e) { setErr(errText(e, "Could not save")); }
    setSaving(false);
  };
  const addLog = async () => {
    setSaving(true); setErr("");
    try {
      const r = await api.post(`/leads/${id}/activity`, { type: log.type, outcome: log.outcome, text: log.text, nextFollowUp: log.nextFollowUp || undefined });
      setLead(r.data.lead); setLog({ type: log.type, outcome: "", text: "", nextFollowUp: "" }); toast.success("Added to the history"); onChanged();
    } catch (e) { setErr(errText(e, "Could not save the note")); }
    setSaving(false);
  };

  const acts = [...(lead?.activities || [])].reverse();
  const inputCls = "mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white outline-none focus:border-[hsl(var(--primary))]";
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl rounded-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{lead ? lead.name : "Lead"}</DialogTitle></DialogHeader>
        {err && <div className="rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-[12.5px] p-3">{err}</div>}
        {!lead && !err && <div className="text-[13px] text-slate-500 py-8 text-center">Loading…</div>}
        {lead && (
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge value={lead.status} />
                {telLink(lead.phone) && <a href={telLink(lead.phone)} className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-slate-200 text-[12.5px] hover:bg-slate-50"><Phone size={13} /> Call</a>}
                {waLink(lead.phone, lead.name) && <a href={waLink(lead.phone, lead.name)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-slate-200 text-[12.5px] hover:bg-slate-50"><MessageCircle size={13} /> WhatsApp</a>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-[11.5px] font-medium text-slate-600">Status
                  <select value={val("status")} onChange={(e) => setEdit({ ...edit, status: e.target.value })} className={inputCls}>{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
                </label>
                <label className="text-[11.5px] font-medium text-slate-600">Owner
                  <select value={val("assignedTo")} onChange={(e) => setEdit({ ...edit, assignedTo: e.target.value })} className={inputCls}>
                    <option value="">Nobody</option>{agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </label>
                <label className="text-[11.5px] font-medium text-slate-600">Next follow-up
                  <input type="date" value={(val("followUpDate") || "").slice(0, 10)} onChange={(e) => setEdit({ ...edit, followUpDate: e.target.value })} className={inputCls} />
                </label>
                <label className="text-[11.5px] font-medium text-slate-600">Phone
                  <input value={val("phone")} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} className={inputCls} />
                </label>
                <label className="text-[11.5px] font-medium text-slate-600 col-span-2">Email
                  <input value={val("email")} onChange={(e) => setEdit({ ...edit, email: e.target.value })} className={inputCls} />
                </label>
                {val("status") === "LOST" && (
                  <label className="text-[11.5px] font-medium text-slate-600 col-span-2">Why was it lost?*
                    <input value={val("lostReason")} onChange={(e) => setEdit({ ...edit, lostReason: e.target.value })} placeholder="e.g. too expensive, not interested" className={inputCls} />
                  </label>
                )}
              </div>
              {lead.notes && <div className="text-[12px] text-slate-600 whitespace-pre-line bg-slate-50 rounded-xl p-3">{lead.notes}</div>}
              <button disabled={!changed || saving} onClick={saveEdit} className="px-3 h-10 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] disabled:opacity-50">{saving ? "Saving…" : "Save changes"}</button>
            </div>
            <div className="space-y-3">
              <div className="rounded-xl border border-slate-200 p-3 space-y-2">
                <div className="text-[12px] font-semibold text-slate-700">Log a call or note</div>
                <div className="grid grid-cols-2 gap-2">
                  <select value={log.type} onChange={(e) => setLog({ ...log, type: e.target.value })} className={inputCls + " mt-0"}>
                    <option value="call">Call</option><option value="whatsapp">WhatsApp</option><option value="visit">Visit</option><option value="note">Note</option>
                  </select>
                  {log.type === "call" ? (
                    <select value={log.outcome} onChange={(e) => setLog({ ...log, outcome: e.target.value })} className={inputCls + " mt-0"}>
                      {CALL_RESULTS.map((o) => <option key={o} value={o}>{o || "Result of the call"}</option>)}
                    </select>
                  ) : <div />}
                </div>
                <textarea value={log.text} onChange={(e) => setLog({ ...log, text: e.target.value })} rows={2} placeholder="What was said?" className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
                <div className="flex items-end gap-2">
                  <label className="text-[11.5px] font-medium text-slate-600 flex-1">Next follow-up
                    <input type="date" value={log.nextFollowUp} onChange={(e) => setLog({ ...log, nextFollowUp: e.target.value })} className={inputCls} />
                  </label>
                  <button disabled={saving || (!log.text.trim() && !log.outcome)} onClick={addLog} className="px-3 h-10 rounded-lg border border-slate-200 bg-white text-[13px] font-medium disabled:opacity-50">Add</button>
                </div>
              </div>
              <div>
                <div className="text-[12px] font-semibold text-slate-700 mb-2">History</div>
                {acts.length === 0 ? <div className="text-[12.5px] text-slate-500">Nothing yet.</div> : (
                  <ol className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {acts.map((a) => (
                      <li key={a.id} className="text-[12.5px] border-l-2 border-slate-200 pl-3">
                        <div className="text-slate-800">
                          <span className="font-medium capitalize">{a.type === "update" ? "Changed" : a.type}</span>
                          {a.outcome ? `: ${a.outcome}` : ""}{a.text ? ` ${a.type === "update" ? "" : "-"} ${a.text}` : ""}
                        </div>
                        <div className="text-[11px] text-slate-500">{a.by || ""} · {a.at ? new Date(a.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: true }) : ""}</div>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function Field({ label, v, on, type = "text", tid }) {
  return (
    <label className="text-[11.5px] font-medium text-slate-600 col-span-1">
      {label}
      <input data-testid={tid} value={v ?? ""} onChange={(e) => on(e.target.value)} type={type} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
    </label>
  );
}
export function SelectField({ label, v, on, opts }) {
  return (
    <label className="text-[11.5px] font-medium text-slate-600">
      {label}
      <select value={v} onChange={(e) => on(e.target.value)} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white outline-none focus:border-[hsl(var(--primary))]">
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
