import React, { useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Trash2, FileText, Search, Info, X } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/glc";
import { PageHeader, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, Btn, Pill, Input, Textarea, Select, Tabs, PhonePreview, errMsg, templateTone } from "./ui";

const blank = { name: "", category: "UTILITY", language: "en", header: "", body: "", footer: "", examples: [], buttons: [] };
const paramCount = (t) => Math.max(0, ...[...(t || "").matchAll(/\{\{\s*(\d+)\s*\}\}/g)].map((m) => Number(m[1])));

const catHelp = {
  UTILITY: "Order updates, account alerts, delivery status. Usually approved fastest.",
  MARKETING: "Offers, deals, announcements. Customers must have opted in.",
  AUTHENTICATION: "One-time passcodes only.",
};

function TemplateDialog({ open, onClose, onCreated }) {
  const [f, setF] = useState(blank);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setF(blank); }, [open]);
  const n = paramCount(f.body);
  const examples = useMemo(() => Array.from({ length: n }, (_, i) => f.examples[i] || ""), [n, f.examples]);
  const preview = useMemo(() => (f.body || "").replace(/\{\{\s*(\d+)\s*\}\}/g, (_, i) => examples[Number(i) - 1] || `{{${i}}}`), [f.body, examples]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setSaving(true);
    try {
      await api.post("/ocm/wa/templates", { ...f, examples });
      toast.success("Sent to Meta for review");
      onCreated();
      onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const setBtn = (i, patch) => setF({ ...f, buttons: f.buttons.map((b, j) => (j === i ? { ...b, ...patch } : b)) });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl rounded-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>New WhatsApp template</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] gap-6">
          <div className="space-y-3">
            <Input label="Template name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} placeholder="glc_order_offer" hint="Lowercase letters, numbers and underscores. It cannot be changed later." />
            <div className="grid grid-cols-2 gap-3">
              <Select label="Category" value={f.category} onChange={set("category")}>
                <option value="UTILITY">Utility</option><option value="MARKETING">Marketing</option><option value="AUTHENTICATION">Authentication</option>
              </Select>
              <Select label="Language" value={f.language} onChange={set("language")}>
                <option value="en">English</option><option value="hi">Hindi</option><option value="en_US">English (US)</option><option value="bn">Bengali</option>
              </Select>
            </div>
            <div className="flex items-start gap-2 text-[11.5px] text-slate-500 bg-slate-50 rounded-lg px-3 py-2"><Info size={13} className="mt-0.5 shrink-0" />{catHelp[f.category]}</div>
            <Input label="Header (optional)" value={f.header} onChange={set("header")} maxLength={60} />
            <Textarea label="Message body" rows={5} value={f.body} onChange={set("body")} maxLength={1024} placeholder={"Hi {{1}}, your order {{2}} is on the way."} hint={`Use {{1}}, {{2}} for variables. ${f.body.length}/1024`} />
            {n > 0 && (
              <div className="space-y-2">
                <div className="text-[12px] font-medium text-slate-600">Sample values (Meta needs these to review)</div>
                {examples.map((v, i) => (
                  <Input key={i} label={`{{${i + 1}}}`} value={v} onChange={(e) => { const next = [...examples]; next[i] = e.target.value; setF({ ...f, examples: next }); }} />
                ))}
              </div>
            )}
            <Input label="Footer (optional)" value={f.footer} onChange={set("footer")} maxLength={60} />
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[12px] font-medium text-slate-600">Buttons (optional, up to 3)</span>
                {f.buttons.length < 3 && <button onClick={() => setF({ ...f, buttons: [...f.buttons, { type: "QUICK_REPLY", text: "" }] })} className="text-[12px] font-medium text-[hsl(var(--primary))]">+ Add button</button>}
              </div>
              <div className="space-y-2">
                {f.buttons.map((b, i) => (
                  <div key={i} className="grid grid-cols-[120px_1fr_1fr_auto] gap-2 items-end">
                    <Select label="" value={b.type} onChange={(e) => setBtn(i, { type: e.target.value })}>
                      <option value="QUICK_REPLY">Reply</option><option value="URL">Link</option><option value="PHONE_NUMBER">Call</option>
                    </Select>
                    <Input label="" placeholder="Button text" value={b.text} onChange={(e) => setBtn(i, { text: e.target.value })} maxLength={25} />
                    {b.type === "URL" ? <Input label="" placeholder="https://" value={b.url || ""} onChange={(e) => setBtn(i, { url: e.target.value })} />
                      : b.type === "PHONE_NUMBER" ? <Input label="" placeholder="+91…" value={b.phone || ""} onChange={(e) => setBtn(i, { phone: e.target.value })} /> : <div />}
                    <button onClick={() => setF({ ...f, buttons: f.buttons.filter((_, j) => j !== i) })} className="h-10 px-2 text-slate-400 hover:text-rose-600"><X size={15} /></button>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="md:sticky md:top-0 self-start">
            <div className="text-[12px] font-medium text-slate-600 mb-2 text-center">Preview</div>
            <PhonePreview header={f.header} body={preview} footer={f.footer} buttons={f.buttons} />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
          <Btn variant="green" onClick={save} loading={saving} disabled={!f.name || !f.body}>Submit for approval</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WaTemplates() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("ALL");
  const [q, setQ] = useState("");
  const [view, setView] = useState(null);

  const load = (refresh = false) => {
    setLoading(true);
    api.get("/ocm/wa/templates", { params: { refresh } })
      .then((r) => { setItems(r.data.items || []); setMeta({ error: r.data.error, live: r.data.live }); })
      .catch((e) => toast.error(errMsg(e)))
      .finally(() => setLoading(false));
  };
  useEffect(() => load(true), []);

  const remove = async (t) => {
    if (!window.confirm(`Delete template "${t.name}"? This removes every language version.`)) return;
    try { await api.delete(`/ocm/wa/templates/${t.name}`); toast.success("Deleted"); load(true); } catch (e) { toast.error(errMsg(e)); }
  };

  const counts = items.reduce((a, t) => ({ ...a, [t.status]: (a[t.status] || 0) + 1 }), {});
  const shown = items.filter((t) => (tab === "ALL" || t.status === tab) && (!q || t.name.includes(q.toLowerCase())));

  return (
    <div className="space-y-6">
      <PageHeader testId="wa-templates" title="Message templates" subtitle="Create templates here and Meta reviews them. Only approved templates can be used in campaigns." actions={
        <>
          <Btn variant="outline" icon={RefreshCw} onClick={() => load(true)} loading={loading}>Sync status</Btn>
          <Btn variant="green" icon={Plus} onClick={() => setOpen(true)}>New template</Btn>
        </>
      } />
      {meta.error && <div className="rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-[13px] px-4 py-3">{meta.error}. Showing saved templates only.</div>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab} onChange={setTab} tabs={[
          { key: "ALL", label: "All", count: items.length },
          { key: "APPROVED", label: "Approved", count: counts.APPROVED || 0 },
          { key: "PENDING", label: "In review", count: (counts.PENDING || 0) + (counts.IN_REVIEW || 0) },
          { key: "REJECTED", label: "Rejected", count: counts.REJECTED || 0 },
        ]} />
        <div className="relative">
          <Search size={14} className="absolute left-3 top-3 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search templates" className="h-10 pl-9 pr-3 rounded-lg border border-slate-200 text-[13px] w-64 outline-none focus:border-[hsl(var(--primary))]" />
        </div>
      </div>

      {!loading && shown.length === 0 ? (
        <EmptyState icon={FileText} title="No templates" description="Create your first template. It usually takes a few minutes to a few hours for Meta to approve." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {shown.map((t) => (
            <Card key={`${t.name}-${t.language}`} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-mono text-[13px] font-medium text-slate-900 truncate">{t.name}</div>
                  <div className="text-[11.5px] text-slate-500 mt-0.5">{t.category} · {t.language}</div>
                </div>
                <Pill tone={templateTone(t.status)}>{(t.status || "").replace("_", " ")}</Pill>
              </div>
              <div className="mt-3 text-[12.5px] text-slate-700 bg-slate-50 rounded-lg p-3 line-clamp-5 whitespace-pre-wrap flex-1">{t.body}</div>
              {t.rejected_reason && t.rejected_reason !== "NONE" && <div className="mt-2 text-[11.5px] text-rose-600">Rejected: {t.rejected_reason.replace(/_/g, " ").toLowerCase()}</div>}
              <div className="mt-3 flex items-center justify-between">
                <span className="text-[11.5px] text-slate-400">{t.paramCount || 0} variable{t.paramCount === 1 ? "" : "s"}</span>
                <div className="flex gap-1">
                  <Btn size="sm" variant="ghost" onClick={() => setView(t)}>Preview</Btn>
                  <Btn size="sm" variant="ghost" icon={Trash2} onClick={() => remove(t)} className="text-rose-600" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <TemplateDialog open={open} onClose={() => setOpen(false)} onCreated={() => load(true)} />
      <Dialog open={!!view} onOpenChange={(v) => !v && setView(null)}>
        <DialogContent className="max-w-sm rounded-2xl">
          <DialogHeader><DialogTitle className="font-mono text-[14px]">{view?.name}</DialogTitle></DialogHeader>
          {view && <PhonePreview
            header={view.components?.find((c) => c.type === "HEADER")?.text}
            body={view.body}
            footer={view.components?.find((c) => c.type === "FOOTER")?.text}
            buttons={view.components?.find((c) => c.type === "BUTTONS")?.buttons || []} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
