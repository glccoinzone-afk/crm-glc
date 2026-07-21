import React, { useEffect, useRef, useState } from "react";
import { Send, Search, MessageSquare, Filter, Circle } from "lucide-react";
import { motion } from "framer-motion";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const CHANNELS = { TELEGRAM: "#0088CC", WHATSAPP: "#25D366", INSTAGRAM: "#E1306C", FACEBOOK: "#1877F2", WEBCHAT: "#064E3B" };

export default function Inbox() {
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [text, setText] = useState("");
  const [filter, setFilter] = useState({ channel: "", q: "" });
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef(null);

  const loadList = () => {
    setLoading(true);
    const params = {};
    if (filter.channel) params.channel = filter.channel;
    api.get("/ocm/conversations", { params }).then((r) => {
      let items = r.data.items || [];
      if (filter.q) items = items.filter((c) => (c.contactName || "").toLowerCase().includes(filter.q.toLowerCase()));
      setConvs(items);
      if (!selected && items[0]) setSelected(items[0].id);
    }).finally(() => setLoading(false));
  };
  useEffect(loadList, [filter.channel]);
  useEffect(() => {
    if (!selected) return;
    api.get(`/ocm/conversations/${selected}`).then((r) => {
      setDetail(r.data);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
    });
  }, [selected]);

  const send = async () => {
    if (!text.trim() || !selected) return;
    const t = text; setText("");
    await api.post(`/ocm/conversations/${selected}/messages`, { text: t, direction: "OUT", channel: detail?.conversation?.channel });
    const r = await api.get(`/ocm/conversations/${selected}`);
    setDetail(r.data);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="inbox-page" title="Omnichannel Inbox" subtitle="Unified shared inbox for Telegram, WhatsApp, Instagram, Facebook & WebChat" />
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 h-[calc(100vh-220px)] min-h-[560px]">
        {/* Conversation list */}
        <div className="bg-white rounded-2xl border border-slate-200/70 card-elev flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-100 space-y-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={filter.q} onChange={(e) => { setFilter({ ...filter, q: e.target.value }); }} placeholder="Search contacts…" className="w-full h-9 pl-8 pr-3 rounded-lg bg-slate-50 border border-transparent focus:bg-white focus:border-slate-200 text-[13px] outline-none" onKeyUp={() => loadList()} />
            </div>
            <div className="flex gap-1 overflow-x-auto">
              {["", ...Object.keys(CHANNELS)].map((c) => (
                <button key={c || "all"} data-testid={`ch-filter-${c || "all"}`} onClick={() => setFilter({ ...filter, channel: c })} className={`px-2.5 py-1 rounded-full text-[11px] font-medium whitespace-nowrap ${filter.channel === c ? "bg-[hsl(var(--primary))] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
                  {c ? c.slice(0, 1) + c.slice(1).toLowerCase() : "All"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && Array.from({ length: 5 }).map((_, i) => (<div key={i} className="p-3 border-b border-slate-50"><div className="glc-skel h-3 w-2/3 mb-2" /><div className="glc-skel h-2.5 w-1/3" /></div>))}
            {!loading && convs.length === 0 && (
              <div className="p-8 text-center text-[13px] text-slate-500">No conversations.</div>
            )}
            {!loading && convs.map((c) => (
              <button
                key={c.id}
                data-testid={`conv-${c.id}`}
                onClick={() => setSelected(c.id)}
                className={`w-full text-left p-3 border-b border-slate-50 hover:bg-slate-50/70 ${selected === c.id ? "bg-slate-50" : ""}`}
              >
                <div className="flex items-start gap-2.5">
                  <Avatar className="w-9 h-9"><AvatarFallback className="text-[11px]" style={{ background: (CHANNELS[c.channel] || "#064E3B") + "22", color: CHANNELS[c.channel] || "#064E3B" }}>{(c.contactName || "?").split(" ").map((s) => s[0]).join("").slice(0, 2)}</AvatarFallback></Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[13px] font-medium text-slate-900 truncate">{c.contactName}</div>
                      <div className="text-[10px] text-slate-400 whitespace-nowrap">{fmtDate(c.lastMessageAt)}</div>
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: CHANNELS[c.channel] || "#064E3B" }} />
                      <span className="text-[10.5px] uppercase tracking-wide text-slate-500 font-medium">{c.channel}</span>
                      {c.unread > 0 && <span className="ml-auto text-[10px] bg-[hsl(var(--accent))] text-white rounded-full px-1.5 py-0.5 font-semibold">{c.unread}</span>}
                    </div>
                    <div className="text-[12px] text-slate-500 truncate mt-1">{c.lastMessage}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Chat window */}
        <div className="bg-white rounded-2xl border border-slate-200/70 card-elev flex flex-col overflow-hidden">
          {!detail && (
            <div className="flex-1 grid place-items-center text-[13px] text-slate-500"><EmptyState icon={MessageSquare} title="Select a conversation" description="Choose a conversation from the list to start chatting." /></div>
          )}
          {detail && (
            <>
              <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="w-9 h-9"><AvatarFallback className="text-[11px]" style={{ background: (CHANNELS[detail.conversation.channel] || "#064E3B") + "22", color: CHANNELS[detail.conversation.channel] || "#064E3B" }}>{(detail.conversation.contactName || "?").split(" ").map((s) => s[0]).join("").slice(0, 2)}</AvatarFallback></Avatar>
                  <div>
                    <div className="text-[14px] font-semibold text-slate-900">{detail.conversation.contactName}</div>
                    <div className="text-[11px] text-slate-500 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{ background: CHANNELS[detail.conversation.channel] || "#064E3B" }} />{detail.conversation.channel} · {detail.contact?.phone || detail.contact?.email || "—"}</div>
                  </div>
                </div>
                <StatusBadge value={detail.conversation.status} />
              </div>
              <div className="flex-1 overflow-y-auto p-5 space-y-3 bg-slate-50/40">
                {(detail.messages || []).map((m) => (
                  <motion.div key={m.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`flex ${m.direction === "OUT" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] rounded-2xl px-3.5 py-2 text-[13.5px] ${m.direction === "OUT" ? "bg-[hsl(var(--primary))] text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                      <div>{m.text}</div>
                      <div className={`text-[10px] mt-1 ${m.direction === "OUT" ? "text-white/60" : "text-slate-400"}`}>{fmtDate(m.createdAt)}</div>
                    </div>
                  </motion.div>
                ))}
                <div ref={bottomRef} />
              </div>
              <div className="p-3 border-t border-slate-100 flex items-center gap-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder={`Reply on ${detail.conversation.channel}…`}
                  className="flex-1 h-10 px-3 rounded-lg border border-slate-200 text-[13.5px] outline-none focus:border-[hsl(var(--primary))]"
                  data-testid="chat-input"
                />
                <button data-testid="chat-send" onClick={send} className="h-10 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px] font-medium inline-flex items-center gap-1.5 hover:bg-[hsl(var(--primary))]/90"><Send size={14} /> Send</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
