import React, { useEffect, useState } from "react";
import { Plus, Users, Send, Megaphone, Bot, CalendarDays, Sparkles, Loader2, Trash2, X } from "lucide-react";
import { motion } from "framer-motion";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState, StatCard } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/pages/crm/Leads";
import { toast } from "sonner";

const CH_COLORS = { TELEGRAM: "#0088CC", WHATSAPP: "#25D366", INSTAGRAM: "#E1306C", FACEBOOK: "#1877F2", WEBCHAT: "#064E3B", YOUTUBE: "#FF0000" };

// ---------- Contacts ----------
export function OcmContacts() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  useEffect(() => {
    setLoading(true);
    api.get("/ocm/contacts", { params: q ? { q } : {} }).then((r) => setRows(r.data.items || [])).finally(() => setLoading(false));
  }, [q]);

  const columns = [
    { key: "name", header: "Contact", render: (r) => (
        <div>
          <div className="font-medium text-slate-900">{r.name}</div>
          <div className="text-[11.5px] text-slate-500">{r.email || r.phone}</div>
        </div>
      )
    },
    { key: "channels", header: "Channels", render: (r) => (
        <div className="flex flex-wrap gap-1">
          {(r.channels || []).map((c) => (
            <span key={c} className="text-[10.5px] font-medium px-1.5 py-0.5 rounded-full" style={{ background: (CH_COLORS[c] || "#94A3B8") + "22", color: CH_COLORS[c] || "#475569" }}>{c}</span>
          ))}
        </div>
      )
    },
    { key: "vertical", header: "Vertical" },
    { key: "tags", header: "Tags", render: (r) => (r.tags || []).join(", ") },
    { key: "subscribed", header: "Subscribed", render: (r) => (
        <span className={`text-[11px] font-medium ${r.subscribed ? "text-emerald-600" : "text-rose-600"}`}>{r.subscribed ? "Yes" : "No"}</span>
      )
    },
    { key: "createdAt", header: "Added", render: (r) => fmtDate(r.createdAt) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="ocm-contacts-page" title="Omnichannel Contacts" subtitle="Unified subscriber list across every communication channel" />
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search contacts…" className="w-full max-w-sm h-10 px-3 rounded-lg bg-white border border-slate-200 text-[13px]" data-testid="ocm-contact-search" />
      {(!loading && rows.length === 0) ? <EmptyState icon={Users} title="No contacts yet" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="ocm-contacts-grid" />}
    </div>
  );
}

// ---------- Broadcasts ----------
const CHANNEL_OPTS = ["TELEGRAM", "WHATSAPP", "INSTAGRAM", "FACEBOOK", "WEBCHAT"];
export function Broadcasts() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", channels: ["TELEGRAM"], audience: "ALL", message: "", status: "DRAFT" });
  const [sending, setSending] = useState({});
  const load = () => { setLoading(true); api.get("/ocm/broadcasts").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);
  const save = async () => { if (!form.name || !form.message) return toast.error("Name & message required"); await api.post("/ocm/broadcasts", form); toast.success("Broadcast saved"); setOpen(false); load(); };
  const send = async (r) => {
    if (sending[r.id]) return;
    setSending((m) => ({ ...m, [r.id]: true }));
    try {
      const res = await api.post(`/ocm/broadcasts/${r.id}/send`);
      const { sent = 0, failed = 0 } = res.data || {};
      if (failed > 0) toast.error(`Sent to ${sent}, ${failed} failed - see Failed column`);
      else toast.success(`Sent to ${sent} contacts`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed");
    } finally {
      setSending((m) => ({ ...m, [r.id]: false }));
      load();
    }
  };
  const toggleCh = (c) => { const has = form.channels.includes(c); setForm({ ...form, channels: has ? form.channels.filter((x) => x !== c) : [...form.channels, c] }); };

  const columns = [
    { key: "name", header: "Broadcast", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "channels", header: "Channels", render: (r) => (
        <div className="flex gap-1">
          {(r.channels || []).map((c) => (<span key={c} className="text-[10.5px] font-medium px-1.5 py-0.5 rounded-full" style={{ background: (CH_COLORS[c] || "#94A3B8") + "22", color: CH_COLORS[c] || "#475569" }}>{c}</span>))}
        </div>
      )
    },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "sentCount", header: "Sent", mono: true, align: "right" },
    { key: "deliveredCount", header: "Accepted", mono: true, align: "right" },
    { key: "failedCount", header: "Failed", mono: true, align: "right", render: (r) => (
        <span title={(r.failureReasons || []).map((f) => `${f.count} x ${f.reason}`).join("\n")} className={r.failedCount > 0 ? "text-red-600 font-medium" : ""}>{r.failedCount ?? 0}</span>
      )
    },
    { key: "readCount", header: "Read", mono: true, align: "right" },
    { key: "actions", header: "", align: "right", render: (r) => r.status === "SENDING" || sending[r.id] ? (
        <span className="text-[11px] text-slate-500">Sending...</span>
      ) : r.status !== "SENT" ? (
        <button data-testid={`broadcast-send-${r.id}`} onClick={() => send(r)} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline">Send now</button>
      ) : <span className="text-[11px] text-emerald-600">Sent</span>
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="broadcasts-page" title="Broadcasts" subtitle="Cross-channel campaigns to your subscribers" actions={
        <button data-testid="new-broadcast-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90"><Plus size={14} /> New Broadcast</button>
      }/>
      {(!loading && rows.length === 0) ? <EmptyState icon={Megaphone} title="No broadcasts yet" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="broadcasts-grid" />}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Broadcast</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Campaign Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="bcast-name" />
            <div>
              <div className="text-[11.5px] font-medium text-slate-600 mb-1">Channels</div>
              <div className="flex gap-2 flex-wrap">
                {CHANNEL_OPTS.map((c) => (
                  <button key={c} data-testid={`bcast-ch-${c.toLowerCase()}`} onClick={() => toggleCh(c)} className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${form.channels.includes(c) ? "text-white" : "bg-slate-100 text-slate-700"}`} style={form.channels.includes(c) ? { background: CH_COLORS[c] } : {}}>{c}</button>
                ))}
              </div>
            </div>
            <SelectField label="Audience" v={form.audience} on={(v) => setForm({ ...form, audience: v })} opts={["ALL", "RETAIL", "WHOLESALE", "DISTRIBUTOR", "VIP"]} />
            <div className="text-[11px] text-slate-400 -mt-2">Filters by customer type; matches CRM contact tags too</div>
            <label className="text-[11.5px] font-medium text-slate-600 block">Message
              <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} rows={4} className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" data-testid="bcast-message" />
            </label>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-broadcast" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Save Draft</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------- Chatbot Flows ----------
const FLOW_TRIGGER_OPTS = ["KEYWORD", "WELCOME"];
const emptyFlowForm = () => ({ name: "", channel: "TELEGRAM", trigger: "KEYWORD", triggerValue: "", status: "DRAFT", steps: [{ type: "MESSAGE", text: "" }] });

export function Flows() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyFlowForm());
  const load = () => { setLoading(true); api.get("/ocm/flows").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);

  const openNew = () => { setEditingId(null); setForm(emptyFlowForm()); setOpen(true); };
  const openEdit = (f) => {
    setEditingId(f.id);
    setForm({
      name: f.name || "",
      channel: f.channel || "TELEGRAM",
      trigger: f.trigger || "KEYWORD",
      triggerValue: f.triggerValue || "",
      status: f.status || "DRAFT",
      steps: (f.steps && f.steps.length > 0) ? f.steps.map((s) => ({ type: s.type || "MESSAGE", text: s.text || "" })) : [{ type: "MESSAGE", text: "" }],
    });
    setOpen(true);
  };

  const save = async () => {
    if (!form.name) return;
    const cleanSteps = form.steps.filter((s) => (s.text || "").trim() !== "");
    const payload = { ...form, steps: cleanSteps.length > 0 ? cleanSteps : [{ type: "MESSAGE", text: "" }] };
    if (editingId) {
      await api.put(`/ocm/flows/${editingId}`, payload);
      toast.success("Flow updated");
    } else {
      await api.post("/ocm/flows", payload);
      toast.success("Flow created");
    }
    setOpen(false);
    load();
  };

  const toggleStatus = async (r) => { const ns = r.status === "ACTIVE" ? "PAUSED" : "ACTIVE"; await api.put(`/ocm/flows/${r.id}`, { status: ns }); toast.success(ns); load(); };

  const addStep = () => setForm({ ...form, steps: [...form.steps, { type: "MESSAGE", text: "" }] });
  const removeStep = (i) => setForm({ ...form, steps: form.steps.filter((_, idx) => idx !== i) });
  const updateStep = (i, text) => setForm({ ...form, steps: form.steps.map((s, idx) => (idx === i ? { ...s, text } : s)) });
  const moveStep = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= form.steps.length) return;
    const next = [...form.steps];
    [next[i], next[j]] = [next[j], next[i]];
    setForm({ ...form, steps: next });
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="flows-page" title="Chatbot Flows" subtitle="Automated conversation flows across your channels" actions={
        <button data-testid="new-flow-btn" onClick={openNew} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90"><Plus size={14} /> New Flow</button>
      }/>
      {(!loading && rows.length === 0) ? <EmptyState icon={Bot} title="No flows yet" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {rows.map((f) => (
            <div key={f.id} className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5">
              <div className="flex items-center justify-between">
                <div className="text-[14px] font-semibold text-slate-900">{f.name}</div>
                <StatusBadge value={f.status} />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10.5px] font-medium px-1.5 py-0.5 rounded-full" style={{ background: (CH_COLORS[f.channel] || "#94A3B8") + "22", color: CH_COLORS[f.channel] || "#475569" }}>{f.channel}</span>
                <span className="text-[11px] text-slate-500">{f.trigger} · <span className="font-mono">{f.triggerValue}</span></span>
              </div>
              <div className="mt-3 space-y-1.5">
                {(f.steps || []).slice(0, 4).map((s, i) => (
                  <div key={i} className="text-[12px] px-2.5 py-1.5 bg-slate-50 border border-slate-100 rounded-lg">
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mr-1.5">{s.type}</span>
                    <span className="text-slate-700">{s.text || (s.options ? `${s.options.length} branch(es)` : "—")}</span>
                  </div>
                ))}
                {(f.steps || []).length > 4 && <div className="text-[11px] text-slate-400">+{f.steps.length - 4} more steps</div>}
              </div>
              <div className="mt-4 flex justify-between items-center">
                <div className="text-[10.5px] text-slate-400">Created {fmtDate(f.createdAt)}</div>
                <div className="flex items-center gap-3">
                  <button data-testid={`flow-edit-${f.id}`} onClick={() => openEdit(f)} className="text-[11.5px] font-medium text-slate-500 hover:underline">Edit</button>
                  <button data-testid={`flow-toggle-${f.id}`} onClick={() => toggleStatus(f)} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline">{f.status === "ACTIVE" ? "Pause" : "Activate"}</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingId ? "Edit Chatbot Flow" : "New Chatbot Flow"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Flow Name*" v={form.name} on={(v) => setForm({ ...form, name: v })} tid="flow-name" />
            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Channel" v={form.channel} on={(v) => setForm({ ...form, channel: v })} opts={CHANNEL_OPTS} />
              <SelectField label="Trigger" v={form.trigger} on={(v) => setForm({ ...form, trigger: v })} opts={FLOW_TRIGGER_OPTS} />
            </div>
            {form.trigger === "KEYWORD" && (
              <Field label="Trigger Keyword*" v={form.triggerValue} on={(v) => setForm({ ...form, triggerValue: v })} />
            )}
            {form.trigger === "WELCOME" && (
              <div className="text-[11.5px] text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">Runs automatically on a contact's first message — no keyword needed.</div>
            )}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11.5px] font-medium text-slate-600">Messages (sent in order)</span>
                <button type="button" onClick={addStep} className="text-[11.5px] font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1"><Plus size={12} /> Add Step</button>
              </div>
              <div className="space-y-2">
                {form.steps.map((s, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-[10.5px] font-semibold text-slate-400 mt-2.5 w-4 text-right">{i + 1}</span>
                    <textarea
                      value={s.text}
                      onChange={(e) => updateStep(i, e.target.value)}
                      rows={2}
                      placeholder={`Step ${i + 1} message…`}
                      className="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-[13px]"
                    />
                    <div className="flex flex-col gap-1 mt-0.5">
                      <button type="button" onClick={() => moveStep(i, -1)} disabled={i === 0} className="text-[10px] text-slate-400 hover:text-slate-600 disabled:opacity-30">▲</button>
                      <button type="button" onClick={() => moveStep(i, 1)} disabled={i === form.steps.length - 1} className="text-[10px] text-slate-400 hover:text-slate-600 disabled:opacity-30">▼</button>
                    </div>
                    <button type="button" onClick={() => removeStep(i)} disabled={form.steps.length === 1} className="text-slate-400 hover:text-red-500 disabled:opacity-30 mt-1.5"><X size={14} /></button>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-flow" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">{editingId ? "Save Changes" : "Create Flow"}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------- Social Scheduler ----------
export function SocialScheduler() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ caption: "", hashtags: [], channels: ["INSTAGRAM"], scheduledAt: "", status: "SCHEDULED" });
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const load = () => api.get("/ocm/social-posts").then((r) => setRows(r.data.items || []));
  useEffect(load, []);
  const save = async () => { if (!form.caption) return toast.error("Caption required"); await api.post("/ocm/social-posts", { ...form, hashtags: form.hashtags }); toast.success("Post scheduled"); setOpen(false); load(); };
  const del = async (r) => { await api.delete(`/ocm/social-posts/${r.id}`); toast.success("Deleted"); load(); };
  const toggleCh = (c) => { const has = form.channels.includes(c); setForm({ ...form, channels: has ? form.channels.filter((x) => x !== c) : [...form.channels, c] }); };

  const genAi = async () => {
    if (!aiPrompt.trim()) return toast.error("Add a short prompt first");
    setAiLoading(true);
    try {
      const r = await api.post("/ai/caption", { prompt: aiPrompt, tone: "friendly", channel: form.channels[0] || "INSTAGRAM" });
      setForm({ ...form, caption: r.data.caption || form.caption, hashtags: r.data.hashtags || [] });
      toast.success("AI caption generated");
    } catch { toast.error("AI generation failed"); }
    setAiLoading(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="social-page" title="Social Scheduler" subtitle="Schedule posts across Instagram, Facebook, Telegram & YouTube" actions={
        <button data-testid="new-post-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90"><Plus size={14} /> New Post</button>
      }/>
      {rows.length === 0 ? <EmptyState icon={Send} title="No scheduled posts" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="social-grid">
          {rows.map((p) => (
            <div key={p.id} className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5">
              <div className="flex items-center justify-between mb-2">
                <StatusBadge value={p.status} />
                <button onClick={() => del(p)} className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-rose-600"><Trash2 size={13} /></button>
              </div>
              <div className="text-[13.5px] text-slate-800 leading-relaxed">{p.caption}</div>
              {(p.hashtags || []).length > 0 && <div className="text-[11.5px] text-[hsl(var(--primary))] mt-2">{p.hashtags.join(" ")}</div>}
              <div className="mt-3 flex items-center justify-between">
                <div className="flex gap-1">
                  {(p.channels || []).map((c) => (<span key={c} className="w-6 h-6 rounded-md grid place-items-center text-[10px] font-semibold" style={{ background: (CH_COLORS[c] || "#94A3B8") + "22", color: CH_COLORS[c] || "#475569" }}>{c[0]}</span>))}
                </div>
                <div className="text-[10.5px] text-slate-400">{p.scheduledAt ? fmtDate(p.scheduledAt) : "—"}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader><DialogTitle>New Social Post</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-1.5 flex items-center gap-1.5"><Sparkles size={12} /> AI Caption Generator</div>
              <div className="flex gap-2">
                <input value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)} placeholder="e.g. Diwali offer Dhani Jewellers 20% off" className="flex-1 h-9 px-3 rounded-md border border-slate-200 text-[13px] bg-white" data-testid="ai-prompt" />
                <button data-testid="ai-generate" onClick={genAi} disabled={aiLoading} className="h-9 px-3 rounded-md bg-[hsl(var(--primary))] text-white text-[12px] font-medium inline-flex items-center gap-1.5 disabled:opacity-60">
                  {aiLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} Generate
                </button>
              </div>
            </div>
            <label className="text-[11.5px] font-medium text-slate-600 block">Caption*
              <textarea value={form.caption} onChange={(e) => setForm({ ...form, caption: e.target.value })} rows={4} className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-[13px]" data-testid="post-caption" />
            </label>
            <label className="text-[11.5px] font-medium text-slate-600 block">Hashtags
              <input value={(form.hashtags || []).join(" ")} onChange={(e) => setForm({ ...form, hashtags: e.target.value.split(/\s+/).filter(Boolean) })} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px]" placeholder="#tag1 #tag2" />
            </label>
            <div>
              <div className="text-[11.5px] font-medium text-slate-600 mb-1">Channels</div>
              <div className="flex gap-2 flex-wrap">
                {CHANNEL_OPTS.concat(["YOUTUBE"]).map((c) => (
                  <button key={c} onClick={() => toggleCh(c)} className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${form.channels.includes(c) ? "text-white" : "bg-slate-100 text-slate-700"}`} style={form.channels.includes(c) ? { background: CH_COLORS[c] || "#064E3B" } : {}}>{c}</button>
                ))}
              </div>
            </div>
            <Field label="Scheduled At (ISO)" v={form.scheduledAt} on={(v) => setForm({ ...form, scheduledAt: v })} type="datetime-local" />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-post" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Schedule</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------- Content Calendar ----------
export function ContentCalendar() {
  const [rows, setRows] = useState([]);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  useEffect(() => { api.get("/ocm/social-posts").then((r) => setRows(r.data.items || [])); }, []);
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const startWeekday = first.getDay();
  const daysInMonth = new Date(y, m, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(y, m - 1, d));
  const postsForDay = (d) => rows.filter((p) => p.scheduledAt && new Date(p.scheduledAt).toDateString() === d.toDateString());

  return (
    <div className="space-y-6">
      <PageHeader testId="calendar-page" title="Content Calendar" subtitle="Bird's-eye view of every scheduled post" actions={
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white" />
      }/>
      <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-4">
        <div className="grid grid-cols-7 gap-2 mb-2">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => <div key={d} className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 text-center">{d}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-2">
          {cells.map((d, i) => (
            <div key={i} className={`min-h-[110px] rounded-xl border ${d ? "border-slate-100" : "border-transparent"} p-2 ${d ? "bg-slate-50/40" : ""}`}>
              {d && (<>
                <div className="text-[11px] font-mono text-slate-500">{d.getDate()}</div>
                <div className="mt-1 space-y-1">
                  {postsForDay(d).slice(0, 3).map((p) => (
                    <div key={p.id} className="text-[10.5px] px-1.5 py-1 rounded bg-white border border-slate-200 truncate" title={p.caption} style={{ borderLeft: `3px solid ${CH_COLORS[p.channels?.[0]] || "#064E3B"}` }}>
                      {p.caption.slice(0, 30)}{p.caption.length > 30 ? "…" : ""}
                    </div>
                  ))}
                  {postsForDay(d).length > 3 && <div className="text-[10px] text-slate-400">+{postsForDay(d).length - 3} more</div>}
                </div>
              </>)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
