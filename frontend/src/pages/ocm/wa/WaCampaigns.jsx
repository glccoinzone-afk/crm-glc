import React, { useEffect, useMemo, useState } from "react";
import { Plus, Megaphone, Send, CalendarClock, Users, ChevronLeft, Check, X } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/glc";
import { PageHeader, EmptyState } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, Btn, Pill, Input, Select, Tabs, TagInput, PhonePreview, MediaPicker, Progress, pct, errMsg, campaignTone, fmtDateTime } from "./ui";

const VARIABLES = ["{{name}}", "{{first_name}}", "{{phone}}"];

function Wizard({ open, onClose, onDone }) {
  const [step, setStep] = useState(0);
  const [templates, setTemplates] = useState([]);
  const [segments, setSegments] = useState([]);
  const [tags, setTags] = useState([]);
  const [f, setF] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [media, setMedia] = useState(null);

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setMedia(null);
    setF({ name: "", templateKey: "", params: [], audienceMode: "segment", segmentId: "", seg: { tags: [], anyTags: [], excludeTags: [], vertical: "ALL" }, when: "now", scheduledAt: "" });
    api.get("/ocm/wa/templates").then((r) => setTemplates((r.data.items || []).filter((t) => t.status === "APPROVED")));
    api.get("/ocm/segments").then((r) => setSegments(r.data.items || []));
    api.get("/ocm/contacts-tags").then((r) => setTags(r.data.items || []));
  }, [open]);

  const tpl = useMemo(() => templates.find((t) => `${t.name}|${t.language}` === f?.templateKey), [templates, f?.templateKey]);
  const audienceBody = useMemo(() => (f?.audienceMode === "segment" && f.segmentId ? { segmentId: f.segmentId } : { segment: f?.seg }), [f]);

  useEffect(() => {
    if (!open || step !== 1 || !f) return;
    const t = setTimeout(() => api.post("/ocm/wa/audience-preview", audienceBody).then((r) => setPreview(r.data)).catch(() => setPreview(null)), 250);
    return () => clearTimeout(t);
  }, [open, step, audienceBody]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!f) return null;
  const n = tpl?.paramCount || 0;
  const params = Array.from({ length: n }, (_, i) => f.params[i] ?? "");
  const rendered = (tpl?.body || "").replace(/\{\{\s*(\d+)\s*\}\}/g, (_, i) => (params[Number(i) - 1] || `{{${i}}}`).replace("{{name}}", "Rohit Kumar").replace("{{first_name}}", "Rohit").replace("{{phone}}", "919608261539"));

  const needsMedia = ["IMAGE", "VIDEO", "DOCUMENT"].includes(tpl?.headerFormat);
  const canNext = [
    () => f.name.trim() && tpl && params.every((p) => p.trim()) && (!needsMedia || media),
    () => preview && preview.count > 0,
    () => f.when === "now" || f.scheduledAt,
  ][step]();

  const submit = async (sendNow) => {
    setBusy(true);
    try {
      const body = {
        name: f.name, templateName: tpl.name, language: tpl.language, params,
        ...audienceBody,
        mediaFileId: needsMedia ? media?.id : null,
        scheduledAt: f.when === "later" ? new Date(f.scheduledAt).toISOString() : null,
      };
      const { data } = await api.post("/ocm/wa/campaigns", body);
      if (sendNow) {
        const r = await api.post(`/ocm/wa/campaigns/${data.id}/send`);
        toast.success(`Sent to ${r.data.sent}${r.data.failed ? `, ${r.data.failed} failed` : ""}`);
      } else toast.success(f.when === "later" ? "Campaign scheduled" : "Saved as draft");
      onDone();
      onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  const steps = ["Message", "Audience", "Send"];
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl rounded-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>New campaign</DialogTitle></DialogHeader>
        <ol className="flex items-center gap-2 text-[12px]">
          {steps.map((s, i) => (
            <li key={s} className="flex items-center gap-2">
              <span className={`w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold ${i < step ? "bg-emerald-500 text-white" : i === step ? "bg-[hsl(var(--primary))] text-white" : "bg-slate-100 text-slate-500"}`}>{i < step ? <Check size={12} /> : i + 1}</span>
              <span className={i === step ? "font-medium text-slate-900" : "text-slate-500"}>{s}</span>
              {i < steps.length - 1 && <span className="w-8 h-px bg-slate-200" />}
            </li>
          ))}
        </ol>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] gap-6 mt-2">
          <div className="space-y-4">
            {step === 0 && (
              <>
                <Input label="Campaign name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Diwali offer – retail customers" />
                <Select label="Template" value={f.templateKey} onChange={(e) => setF({ ...f, templateKey: e.target.value, params: [] })}>
                  <option value="">Choose an approved template…</option>
                  {templates.map((t) => <option key={`${t.name}|${t.language}`} value={`${t.name}|${t.language}`}>{t.name} ({t.language})</option>)}
                </Select>
                {templates.length === 0 && <div className="text-[12px] text-amber-700 bg-amber-50 rounded-lg px-3 py-2">No approved templates yet. Create one on the Templates page and wait for Meta to approve it.</div>}
                {needsMedia && (
                  <div><div className="text-[12px] font-medium text-slate-600 mb-1">This template has a {tpl.headerFormat.toLowerCase()} header. Choose the file to send</div>
                    <MediaPicker format={tpl.headerFormat} value={media} onChange={setMedia} label={`Choose ${tpl.headerFormat.toLowerCase()}`} /></div>
                )}
                {n > 0 && (
                  <div className="space-y-2">
                    <div className="text-[12px] font-medium text-slate-600">Fill the variables</div>
                    {params.map((p, i) => (
                      <div key={i}>
                        <Input label={`{{${i + 1}}}`} value={p} onChange={(e) => { const next = [...params]; next[i] = e.target.value; setF({ ...f, params: next }); }} placeholder="Type text or pick a field below" />
                        <div className="flex gap-1 mt-1">
                          {VARIABLES.map((v) => <button key={v} onClick={() => { const next = [...params]; next[i] = (next[i] || "") + v; setF({ ...f, params: next }); }} className="text-[11px] px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600 hover:bg-slate-200 font-mono">{v}</button>)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {step === 1 && (
              <>
                <Tabs value={f.audienceMode} onChange={(v) => setF({ ...f, audienceMode: v })} tabs={[{ key: "segment", label: "Saved segment" }, { key: "custom", label: "Pick by tags" }]} />
                {f.audienceMode === "segment" ? (
                  <Select label="Segment" value={f.segmentId} onChange={(e) => setF({ ...f, segmentId: e.target.value })}>
                    <option value="">Everyone who can receive messages</option>
                    {segments.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.count})</option>)}
                  </Select>
                ) : (
                  <div className="space-y-3">
                    <div><div className="text-[12px] font-medium text-slate-600 mb-1">Has any of these tags</div><TagInput value={f.seg.anyTags} suggestions={tags} onChange={(v) => setF({ ...f, seg: { ...f.seg, anyTags: v } })} /></div>
                    <div><div className="text-[12px] font-medium text-slate-600 mb-1">Has all of these tags</div><TagInput value={f.seg.tags} suggestions={tags} onChange={(v) => setF({ ...f, seg: { ...f.seg, tags: v } })} /></div>
                    <div><div className="text-[12px] font-medium text-slate-600 mb-1">Exclude contacts with</div><TagInput value={f.seg.excludeTags} suggestions={tags} onChange={(v) => setF({ ...f, seg: { ...f.seg, excludeTags: v } })} /></div>
                  </div>
                )}
                <Card className="bg-emerald-50/60 border-emerald-100">
                  <div className="flex items-center gap-2"><Users size={16} className="text-emerald-700" /><span className="text-[22px] font-semibold text-emerald-800 tabular">{preview ? preview.count : "…"}</span><span className="text-[13px] text-emerald-800">people will receive this</span></div>
                  {preview?.sample?.length > 0 && <div className="text-[12px] text-emerald-800/80 mt-1">e.g. {preview.sample.map((s) => s.name).join(", ")}</div>}
                  <div className="text-[11.5px] text-emerald-800/70 mt-1">Opted-out contacts are always left out.</div>
                </Card>
              </>
            )}

            {step === 2 && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  {[{ k: "now", icon: Send, t: "Send now", d: "Starts right away" }, { k: "later", icon: CalendarClock, t: "Schedule", d: "Pick a date and time" }].map((o) => (
                    <button key={o.k} onClick={() => setF({ ...f, when: o.k })} className={`text-left rounded-xl border p-4 transition-colors ${f.when === o.k ? "border-[hsl(var(--primary))] bg-[hsl(158_64%_96%)]" : "border-slate-200 hover:border-slate-300"}`}>
                      <o.icon size={18} className="text-[hsl(var(--primary))]" />
                      <div className="text-[13.5px] font-semibold mt-2">{o.t}</div>
                      <div className="text-[12px] text-slate-500">{o.d}</div>
                    </button>
                  ))}
                </div>
                {f.when === "later" && <Input label="Send at" type="datetime-local" value={f.scheduledAt} onChange={(e) => setF({ ...f, scheduledAt: e.target.value })} />}
                <Card className="bg-slate-50 border-slate-200">
                  <div className="text-[12.5px] text-slate-700 space-y-1">
                    <div><b>{f.name}</b></div>
                    <div>Template: <span className="font-mono">{tpl?.name}</span></div>
                    <div>Recipients: <b>{preview?.count ?? "—"}</b></div>
                  </div>
                </Card>
              </>
            )}
          </div>
          <div className="md:sticky md:top-0 self-start"><PhonePreview body={rendered} footer={tpl?.components?.find((c) => c.type === "FOOTER")?.text} header={needsMedia ? "" : tpl?.components?.find((c) => c.type === "HEADER")?.text} media={needsMedia ? { format: tpl.headerFormat, url: media?.url, name: media?.filename } : null} /></div>
        </div>

        <div className="flex justify-between pt-2">
          <Btn variant="ghost" icon={step > 0 ? ChevronLeft : undefined} onClick={() => (step > 0 ? setStep(step - 1) : onClose())}>{step > 0 ? "Back" : "Cancel"}</Btn>
          {step < 2 ? <Btn onClick={() => setStep(step + 1)} disabled={!canNext}>Continue</Btn> : (
            <div className="flex gap-2">
              <Btn variant="outline" onClick={() => submit(false)} loading={busy} disabled={!canNext}>{f.when === "later" ? "Schedule" : "Save draft"}</Btn>
              {f.when === "now" && <Btn variant="green" icon={Send} onClick={() => window.confirm(`Send to ${preview?.count} people now?`) && submit(true)} loading={busy}>Send now</Btn>}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Detail({ id, onClose, onChanged }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    if (!id) return setD(null);
    const load = () => api.get(`/ocm/wa/campaigns/${id}`).then((r) => setD(r.data));
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [id]);
  const c = d?.campaign;
  const s = c?.stats;
  const act = async (path, ok) => { try { await api.post(`/ocm/wa/campaigns/${id}/${path}`); toast.success(ok); onChanged(); onClose(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Dialog open={!!id} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl rounded-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{c?.name || "Campaign"}</DialogTitle></DialogHeader>
        {c && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-[12px] text-slate-500"><Pill tone={campaignTone(c.status)}>{c.status}</Pill><span className="font-mono">{c.templateName}</span><span>· {fmtDateTime(c.scheduledAt || c.createdAt)}</span></div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[["Sent", s.sent, s.total], ["Delivered", s.delivered, s.sent], ["Read", s.read, s.sent], ["Failed", s.failed, s.total]].map(([l, v, t]) => (
                <Card key={l}><div className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">{l}</div><div className="text-[22px] font-semibold tabular">{v}</div><Progress value={pct(v, t)} tone={l === "Failed" ? "bg-rose-400" : "bg-[#25D366]"} /><div className="text-[11px] text-slate-400 mt-1">{pct(v, t)}%</div></Card>
              ))}
            </div>
            {c.failureReasons?.length > 0 && <div className="rounded-xl bg-rose-50 text-rose-700 text-[12.5px] p-3 space-y-0.5">{c.failureReasons.map((f) => <div key={f.reason}>{f.count} × {f.reason}</div>)}</div>}
            {["DRAFT", "SCHEDULED"].includes(c.status) && (
              <div className="flex gap-2">
                <Btn variant="green" icon={Send} onClick={() => window.confirm("Send this campaign now?") && act("send", "Campaign sent")}>Send now</Btn>
                <Btn variant="danger" icon={X} onClick={() => act("cancel", "Cancelled")}>Cancel campaign</Btn>
              </div>
            )}
            <div className="rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-[12.5px]">
                <thead><tr className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500"><th className="px-3 py-2">Number</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Detail</th></tr></thead>
                <tbody>
                  {(d.messages || []).slice(0, 100).map((m) => (
                    <tr key={m.id} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{m.to}</td>
                      <td className="px-3 py-2"><Pill tone={m.status === "FAILED" ? "red" : m.status === "READ" ? "violet" : m.status === "DELIVERED" ? "green" : "slate"}>{m.status}</Pill></td>
                      <td className="px-3 py-2 text-slate-500">{m.error || fmtDateTime(m.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function WaCampaigns() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizard, setWizard] = useState(false);
  const [openId, setOpenId] = useState(null);
  const load = () => api.get("/ocm/wa/campaigns").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  return (
    <div className="space-y-6">
      <PageHeader testId="wa-campaigns" title="Campaigns" subtitle="Send an approved template to a segment now or at a scheduled time" actions={<Btn variant="green" icon={Plus} onClick={() => setWizard(true)}>New campaign</Btn>} />
      {!loading && rows.length === 0 ? (
        <EmptyState icon={Megaphone} title="No campaigns yet" description="Pick an approved template and an audience to send your first campaign." action={<Btn variant="green" icon={Plus} onClick={() => setWizard(true)}>New campaign</Btn>} />
      ) : (
        <Card pad={false}>
          <div className="divide-y divide-slate-100">
            {rows.map((c) => (
              <button key={c.id} onClick={() => setOpenId(c.id)} className="w-full text-left px-5 py-4 hover:bg-slate-50/70 transition-colors">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[14px] font-medium text-slate-900 truncate">{c.name}</div>
                    <div className="text-[12px] text-slate-500 mt-0.5"><span className="font-mono">{c.templateName}</span> · {c.status === "SCHEDULED" ? `Scheduled ${fmtDateTime(c.scheduledAt)}` : fmtDateTime(c.createdAt)} · {c.createdBy}</div>
                  </div>
                  <Pill tone={campaignTone(c.status)}>{c.status}</Pill>
                </div>
                {c.stats?.total > 0 && (
                  <div className="mt-3 grid grid-cols-4 gap-4 max-w-xl">
                    {[["Sent", c.stats.sent, c.stats.total], ["Delivered", c.stats.delivered, c.stats.sent], ["Read", c.stats.read, c.stats.sent], ["Failed", c.stats.failed, c.stats.total]].map(([l, v, t]) => (
                      <div key={l}><div className="flex justify-between text-[11px] text-slate-500"><span>{l}</span><span className="tabular">{v}</span></div><Progress value={pct(v, t)} tone={l === "Failed" ? "bg-rose-400" : "bg-[#25D366]"} /></div>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        </Card>
      )}
      <Wizard open={wizard} onClose={() => setWizard(false)} onDone={load} />
      <Detail id={openId} onClose={() => setOpenId(null)} onChanged={load} />
    </div>
  );
}
