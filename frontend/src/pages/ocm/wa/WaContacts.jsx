import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, Upload, Search, Tag, Users, Trash2, BellOff, Bell, Download, Layers } from "lucide-react";
import { toast } from "sonner";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, Btn, Pill, Input, TagInput, TagChip, Tabs, errMsg } from "./ui";

const SAMPLE = "name,phone,email,tags,vertical\nRohit Kumar,9608261539,rohit@example.com,vip;retail,GLC Fresh\n";

function ImportDialog({ open, onClose, onDone }) {
  const [text, setText] = useState("");
  const [tags, setTags] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  useEffect(() => { if (open) { setText(""); setTags([]); setResult(null); } }, [open]);

  const pick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const r = new FileReader();
    r.onload = () => setText(String(r.result || ""));
    r.readAsText(file);
  };
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/ocm/contacts-import", { csv: text, tags });
      setResult(data);
      onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const lines = text ? Math.max(0, text.trim().split(/\r?\n/).length - 1) : 0;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg rounded-2xl">
        <DialogHeader><DialogTitle>Import contacts from CSV</DialogTitle></DialogHeader>
        {!result ? (
          <div className="space-y-4">
            <div className="rounded-xl border-2 border-dashed border-slate-200 p-6 text-center">
              <Upload className="mx-auto text-slate-400" size={22} />
              <div className="text-[13px] text-slate-700 mt-2">{text ? `${lines} row${lines === 1 ? "" : "s"} ready to import` : "Choose a .csv file"}</div>
              <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={pick} className="hidden" />
              <div className="mt-3 flex justify-center gap-2">
                <Btn variant="outline" size="sm" onClick={() => fileRef.current?.click()}>Choose file</Btn>
                <a href={`data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`} download="contacts-sample.csv"><Btn variant="ghost" size="sm" icon={Download}>Sample file</Btn></a>
              </div>
              <div className="text-[11.5px] text-slate-400 mt-3">Columns: name, phone, email, tags, vertical. Phone numbers without a country code get +91.</div>
            </div>
            <div>
              <div className="text-[12px] font-medium text-slate-600 mb-1">Add these tags to every imported contact</div>
              <TagInput value={tags} onChange={setTags} placeholder="e.g. diwali-2026" />
            </div>
            <div className="flex justify-end gap-2"><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn variant="green" onClick={run} loading={busy} disabled={!lines}>Import {lines || ""}</Btn></div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3 text-center">
              <Card><div className="text-[22px] font-semibold text-emerald-700">{result.created}</div><div className="text-[11.5px] text-slate-500">New</div></Card>
              <Card><div className="text-[22px] font-semibold text-blue-700">{result.updated}</div><div className="text-[11.5px] text-slate-500">Updated</div></Card>
              <Card><div className="text-[22px] font-semibold text-rose-700">{result.errorCount}</div><div className="text-[11.5px] text-slate-500">Skipped</div></Card>
            </div>
            {result.errors?.length > 0 && (
              <div className="max-h-40 overflow-y-auto rounded-xl bg-rose-50 p-3 text-[12px] text-rose-700 space-y-0.5">
                {result.errors.map((e, i) => <div key={i}>Line {e.line}: {e.reason}{e.value ? ` (${e.value})` : ""}</div>)}
              </div>
            )}
            <div className="flex justify-end"><Btn onClick={onClose}>Done</Btn></div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ContactDialog({ open, contact, allTags, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", phone: "", email: "", tags: [], vertical: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setF({ name: contact?.name || "", phone: contact?.phone || "", email: contact?.email || "", tags: contact?.tags || [], vertical: contact?.vertical || "" });
  }, [open, contact]);
  const save = async () => {
    setBusy(true);
    try {
      if (contact) await api.put(`/ocm/contacts/${contact.id}`, f);
      else await api.post("/ocm/contacts", { ...f, channels: ["WHATSAPP"], whatsappId: f.phone.replace(/\D/g, ""), subscribed: true });
      toast.success("Saved");
      onSaved();
      onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader><DialogTitle>{contact ? "Edit contact" : "Add contact"}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input label="WhatsApp number" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="9608261539" />
          <Input label="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
          <div><div className="text-[12px] font-medium text-slate-600 mb-1">Tags</div><TagInput value={f.tags} onChange={(tags) => setF({ ...f, tags })} suggestions={allTags} /></div>
        </div>
        <div className="flex justify-end gap-2 pt-2"><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn onClick={save} loading={busy} disabled={!f.name || !f.phone}>Save</Btn></div>
      </DialogContent>
    </Dialog>
  );
}

export default function WaContacts() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [status, setStatus] = useState("all");
  const [tags, setTags] = useState([]);
  const [segments, setSegments] = useState([]);
  const [sel, setSel] = useState(new Set());
  const [importing, setImporting] = useState(false);
  const [edit, setEdit] = useState(undefined);
  const [bulkTag, setBulkTag] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api.get("/ocm/contacts", { params: { limit: 500, ...(q ? { q } : {}) } })
      .then((r) => { setRows(r.data.items || []); setTotal(r.data.total || 0); })
      .finally(() => setLoading(false));
    api.get("/ocm/contacts-tags").then((r) => setTags(r.data.items || []));
    api.get("/ocm/segments").then((r) => setSegments(r.data.items || []));
  }, [q]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const shown = useMemo(() => rows.filter((r) =>
    (!tagFilter || (r.tags || []).includes(tagFilter)) &&
    (status === "all" || (status === "optedOut" ? r.optedOut || r.subscribed === false : !(r.optedOut || r.subscribed === false)))), [rows, tagFilter, status]);

  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSel = shown.length > 0 && shown.every((r) => sel.has(r.id));
  const doBulk = async (body) => { try { await api.post("/ocm/contacts-bulk-tag", { ids: [...sel], ...body }); toast.success("Updated"); setBulkTag(""); load(); } catch (e) { toast.error(errMsg(e)); } };
  const opt = async (c) => { await api.post(`/ocm/contacts/${c.id}/opt`, { optedOut: !(c.optedOut || c.subscribed === false) }); load(); };
  const remove = async (c) => { if (window.confirm(`Delete ${c.name}?`)) { await api.delete(`/ocm/contacts/${c.id}`); load(); } };
  const saveSegment = async () => {
    const name = window.prompt("Name this segment");
    if (!name) return;
    try {
      await api.post("/ocm/segments", { name, filter: { anyTags: tagFilter ? [tagFilter] : [], search: q } });
      toast.success("Segment saved");
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="wa-contacts" title="Contacts" subtitle={`${total} contacts across your channels. Tag them to build campaign audiences.`} actions={
        <>
          <Btn variant="outline" icon={Upload} onClick={() => setImporting(true)}>Import CSV</Btn>
          <Btn variant="green" icon={Plus} onClick={() => setEdit(null)}>Add contact</Btn>
        </>
      } />

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        <div className="space-y-4">
          <Card>
            <div className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-700 mb-2"><Tag size={13} /> Tags</div>
            <div className="flex flex-col gap-0.5">
              <button onClick={() => setTagFilter("")} className={`text-left px-2 py-1.5 rounded-md text-[12.5px] ${!tagFilter ? "bg-slate-100 font-medium" : "hover:bg-slate-50 text-slate-600"}`}>All contacts</button>
              {tags.map((t) => (
                <button key={t} onClick={() => setTagFilter(t === tagFilter ? "" : t)} className={`text-left px-2 py-1.5 rounded-md text-[12.5px] truncate ${tagFilter === t ? "bg-slate-100 font-medium" : "hover:bg-slate-50 text-slate-600"}`}>{t}</button>
              ))}
              {tags.length === 0 && <div className="text-[12px] text-slate-400 px-2">No tags yet</div>}
            </div>
          </Card>
          <Card>
            <div className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-700 mb-2"><Layers size={13} /> Segments</div>
            {segments.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-[12.5px] py-1">
                <span className="truncate text-slate-700">{s.name}</span>
                <span className="flex items-center gap-1 text-slate-400"><span className="tabular">{s.count}</span>
                  <button onClick={async () => { await api.delete(`/ocm/segments/${s.id}`); load(); }} className="hover:text-rose-600"><Trash2 size={12} /></button></span>
              </div>
            ))}
            {segments.length === 0 && <div className="text-[12px] text-slate-400">No saved segments</div>}
            <Btn size="sm" variant="soft" className="mt-2 w-full" onClick={saveSegment} disabled={!tagFilter && !q}>Save current filter</Btn>
          </Card>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={status} onChange={setStatus} tabs={[{ key: "all", label: "All" }, { key: "active", label: "Can receive" }, { key: "optedOut", label: "Opted out" }]} />
            <div className="relative"><Search size={14} className="absolute left-3 top-3 text-slate-400" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, phone, email" className="h-10 pl-9 pr-3 rounded-lg border border-slate-200 text-[13px] w-72 outline-none focus:border-[hsl(var(--primary))]" /></div>
          </div>

          {sel.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl bg-slate-900 text-white px-4 py-2.5 text-[13px]">
              <span>{sel.size} selected</span>
              <input value={bulkTag} onChange={(e) => setBulkTag(e.target.value)} placeholder="tag name" className="h-8 px-2 rounded-md bg-white/10 text-[12.5px] outline-none placeholder:text-white/40" />
              <Btn size="sm" variant="green" disabled={!bulkTag} onClick={() => doBulk({ add: [bulkTag] })}>Add tag</Btn>
              <Btn size="sm" variant="soft" disabled={!bulkTag} onClick={() => doBulk({ remove: [bulkTag] })}>Remove tag</Btn>
              <button className="ml-auto text-white/70 hover:text-white text-[12px]" onClick={() => setSel(new Set())}>Clear</button>
            </div>
          )}

          {!loading && shown.length === 0 ? <EmptyState icon={Users} title="No contacts found" description="Import a CSV or add a contact to get started." /> : (
            <Card pad={false}>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead><tr className="bg-slate-50/80 border-b border-slate-200 text-left text-[11px] uppercase tracking-[0.06em] text-slate-500">
                    <th className="px-4 py-3 w-10"><input type="checkbox" checked={allSel} onChange={() => setSel(allSel ? new Set() : new Set(shown.map((r) => r.id)))} /></th>
                    <th className="px-2 py-3">Contact</th><th className="px-2 py-3">Tags</th><th className="px-2 py-3">Status</th><th className="px-2 py-3">Added</th><th className="px-2 py-3" />
                  </tr></thead>
                  <tbody>
                    {loading && <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400">Loading…</td></tr>}
                    {shown.map((c) => {
                      const out = c.optedOut || c.subscribed === false;
                      return (
                        <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50/60">
                          <td className="px-4 py-3"><input type="checkbox" checked={sel.has(c.id)} onChange={() => toggle(c.id)} /></td>
                          <td className="px-2 py-3 cursor-pointer" onClick={() => setEdit(c)}>
                            <div className="font-medium text-slate-900">{c.name}</div>
                            <div className="text-[11.5px] text-slate-500 font-mono">{c.phone || c.email}</div>
                          </td>
                          <td className="px-2 py-3"><div className="flex flex-wrap gap-1">{(c.tags || []).slice(0, 4).map((t) => <TagChip key={t}>{t}</TagChip>)}</div></td>
                          <td className="px-2 py-3"><Pill tone={out ? "red" : "green"}>{out ? "Opted out" : "Subscribed"}</Pill></td>
                          <td className="px-2 py-3 text-slate-500">{fmtDate(c.createdAt)}</td>
                          <td className="px-2 py-3 text-right whitespace-nowrap">
                            <button title={out ? "Opt back in" : "Opt out"} onClick={() => opt(c)} className="p-1.5 text-slate-400 hover:text-slate-700">{out ? <Bell size={14} /> : <BellOff size={14} />}</button>
                            <button onClick={() => remove(c)} className="p-1.5 text-slate-400 hover:text-rose-600"><Trash2 size={14} /></button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      <ImportDialog open={importing} onClose={() => setImporting(false)} onDone={load} />
      <ContactDialog open={edit !== undefined} contact={edit || null} allTags={tags} onClose={() => setEdit(undefined)} onSaved={load} />
    </div>
  );
}
