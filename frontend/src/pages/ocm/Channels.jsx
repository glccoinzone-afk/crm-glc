import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Send, Instagram, Facebook, Globe, ChevronDown, RefreshCw, Check, AlertTriangle, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { fmtNum } from "@/lib/glc";
import { PageHeader } from "@/components/common/GlcUI";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, Btn, Pill, Input, Textarea, errMsg, timeAgo } from "./wa/ui";

const META = {
  WHATSAPP: { icon: MessageCircle, color: "#25D366", link: ["/ocm/whatsapp", "WhatsApp setup"] },
  TELEGRAM: { icon: Send, color: "#0088CC", link: ["/ocm/broadcasts", "Quick Broadcast"] },
  FACEBOOK: { icon: Facebook, color: "#1877F2", link: ["/ocm/social", "Social Scheduler"] },
  INSTAGRAM: { icon: Instagram, color: "#E1306C", link: ["/ocm/social", "Social Scheduler"] },
  WEBCHAT: { icon: Globe, color: "#064E3B", link: ["/ocm/inbox", "Inbox"] },
};

function state(c) {
  if (!c.ready) return { tone: "amber", text: "Not set up", icon: AlertTriangle };
  if (c.live && !c.live.ok) return { tone: "red", text: "Credentials rejected", icon: XCircle };
  return { tone: "green", text: c.live?.name ? `Connected · ${c.live.name}` : "Connected", icon: Check };
}

function TestDialog({ channel, onClose }) {
  const [to, setTo] = useState("");
  const [text, setText] = useState("Test message from GLC Zone CRM");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (channel) { setTo(""); } }, [channel]);
  const send = async () => {
    setBusy(true);
    try { await api.post(`/ocm/channels/${channel.key}/test`, { to, text }); toast.success("Sent"); onClose(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={!!channel} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader><DialogTitle>Send a test on {channel?.label}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input label="Recipient" value={to} onChange={(e) => setTo(e.target.value)} hint={channel?.idHelp} />
          <Textarea label="Message" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          {channel?.key === "WHATSAPP" && <div className="text-[12px] text-amber-700 bg-amber-50 rounded-lg px-3 py-2">WhatsApp delivers free text only if this person wrote to you in the last 24 hours. Otherwise send an approved template from Campaigns.</div>}
        </div>
        <div className="flex justify-end gap-2 pt-2"><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn variant="green" icon={Send} onClick={send} loading={busy} disabled={!to.trim() || !text.trim()}>Send test</Btn></div>
      </DialogContent>
    </Dialog>
  );
}

export default function Channels() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState({});
  const [test, setTest] = useState(null);

  const load = () => { setLoading(true); api.get("/ocm/channels").then((r) => setItems(r.data.items || [])).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false)); };
  useEffect(load, []);

  const connected = items.filter((c) => c.ready && (!c.live || c.live.ok)).length;

  return (
    <div className="space-y-6">
      <PageHeader testId="channels-page" title="Channels" subtitle={`${connected} of ${items.length} channels connected. Each one is checked live with its own credentials.`} actions={<Btn variant="outline" icon={RefreshCw} onClick={load} loading={loading}>Re-check</Btn>} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {items.map((c) => {
          const m = META[c.key] || META.WEBCHAT;
          const st = state(c);
          const Icon = m.icon;
          return (
            <Card key={c.key}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl grid place-items-center text-white" style={{ background: m.color }}><Icon size={20} /></div>
                  <div>
                    <div className="text-[15px] font-semibold text-slate-900">{c.label}</div>
                    <div className="mt-0.5"><Pill tone={st.tone}><st.icon size={11} />{st.text}</Pill></div>
                  </div>
                </div>
                <div className="flex gap-1.5">
                  {c.ready && c.key !== "WEBCHAT" && <Btn size="sm" variant="soft" onClick={() => setTest(c)}>Send test</Btn>}
                  <Link to={m.link[0]}><Btn size="sm" variant="outline">{m.link[1]}</Btn></Link>
                </div>
              </div>

              {c.live && !c.live.ok && <div className="mt-3 text-[12.5px] text-rose-700 bg-rose-50 rounded-lg px-3 py-2 break-words">{c.live.error}</div>}
              {!c.ready && (
                <div className="mt-3 text-[12.5px] text-amber-800 bg-amber-50 rounded-lg px-3 py-2">
                  Missing on the server: {c.missing.map((v) => <code key={v} className="mx-0.5 px-1 py-0.5 rounded bg-white/70 text-[11.5px]">{v}</code>)}
                </div>
              )}
              {c.ready && c.optionalMissing?.length > 0 && <div className="mt-3 text-[12px] text-slate-500">Optional: {c.optionalMissing.join(", ")} (needed to post to a channel)</div>}

              <div className="mt-4 grid grid-cols-4 gap-3 text-center">
                {[["Contacts", c.contacts], ["Chats", c.conversations], ["Msgs 30d", c.messages30], ["Last", c.lastMessageAt ? timeAgo(c.lastMessageAt) : "—"]].map(([l, v]) => (
                  <div key={l} className="rounded-xl bg-slate-50 py-2"><div className="text-[17px] font-semibold tabular text-slate-900">{typeof v === "number" ? fmtNum(v) : v}</div><div className="text-[11px] text-slate-500">{l}</div></div>
                ))}
              </div>

              <div className="mt-4 text-[12.5px] text-slate-600 space-y-1">
                <div><span className="font-medium text-slate-700">Receives: </span>{c.receive}</div>
                <div><span className="font-medium text-slate-700">Sends: </span>{c.send}</div>
              </div>

              <button onClick={() => setOpen({ ...open, [c.key]: !open[c.key] })} className="mt-3 flex items-center gap-1 text-[12.5px] font-medium text-[hsl(var(--primary))]">
                How to connect <ChevronDown size={14} className={open[c.key] ? "rotate-180" : ""} />
              </button>
              {open[c.key] && <ol className="mt-2 text-[12.5px] text-slate-600 list-decimal pl-5 space-y-1">{c.setup.map((s, i) => <li key={i}>{s}</li>)}</ol>}
            </Card>
          );
        })}
      </div>
      <TestDialog channel={test} onClose={() => setTest(null)} />
    </div>
  );
}
