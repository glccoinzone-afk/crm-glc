import React, { useEffect, useRef, useState } from "react";
import { Send, Search, Bot, UserCheck, UserX } from "lucide-react";
import { motion } from "framer-motion";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, EmptyState } from "@/components/common/GlcUI";
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadList, [filter.channel]);

  useEffect(() => {
    const interval = setInterval(() => {
      const params = {};
      if (filter.channel) params.channel = filter.channel;
      api.get("/ocm/conversations", { params }).then((r) => {
        let items = r.data.items || [];
        if (filter.q) items = items.filter((c) => (c.contactName || "").toLowerCase().includes(filter.q.toLowerCase()));
        setConvs(items);
      });
    }, 6000);
    return () => clearInterval(interval);
  }, [filter.channel, filter.q]);

  const loadDetail = (id, scroll) => {
    api.get(`/ocm/conversations/${id}`).then((r) => {
      setDetail(r.data);
      if (scroll) setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
    });
  };

  useEffect(() => {
    if (!selected) return;
    loadDetail(selected, true);
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    const interval = setInterval(() => {
      loadDetail(selected, false);
    }, 4000);
    return () => clearInterval(interval);
  }, [selected]);

  const send = async () => {
    if (!text.trim() || !selected) return;
    const t = text; setText("");
    await api.post(`/ocm/conversations/${selected}/messages`, { text: t, direction: "OUT", channel: detail?.conversation?.channel });
    const r = await api.get(`/ocm/conversations/${selected}`);
    setDetail(r.data);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
  };

  const toggleAgentMode = async () => {
    const current = detail?.conversation?.agentMode;
    await api.put(`/ocm/conversations/${selected}`, { agentMode: !current });
    const r = await api.get(`/ocm/conversations/${selected}`);
    setDetail(r.data);
  };

  const agentMode = detail?.conversation?.agentMode;

  return (
    <div className="space-y-6">
      <PageHeader testId="inbox-page" title="Omnichannel Inbox" subtitle="Unified shared inbox for WhatsApp, Telegram & more" />
      <div className="flex h-[calc(100vh-160px)] rounded-xl border border-slate-200 overflow-hidden bg-white">
        {/* Left: Conversation List */}
        <div className="w-80 border-r border-slate-100 flex flex-col">
          <div className="p-3 border-b border-slate-100 flex gap-2">
            <input value={filter.q} onChange={(e) => setFilter((f) => ({ ...f, q: e.target.value }))} placeholder="Search..." className="flex-1 h-9 px-3 rounded-lg border border-slate-200 text-[13px] outline-none" />
            <select value={filter.channel} onChange={(e) => setFilter((f) => ({ ...f, channel: e.target.value }))} className="h-9 px-2 rounded-lg border border-slate-200 text-[12px] outline-none">
              <option value="">All</option>
              {Object.keys(CHANNELS).map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? <div className="p-4 text-center text-slate-400 text-sm">Loading…</div> : convs.length === 0 ? <EmptyState title="No conversations" /> :
              convs.map((c) => (
                <div key={c.id} onClick={() => setSelected(c.id)} className={`p-3 cursor-pointer border-b border-slate-50 hover:bg-slate-50 ${selected === c.id ? "bg-slate-100" : ""}`}>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-8 w-8"><AvatarFallback className="text-xs">{(c.contactName || "?")[0]}</AvatarFallback></Avatar>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-[13px] font-medium truncate">{c.contactName || "Unknown"}</span>
                        {c.agentMode && <UserCheck size={11} className="text-blue-500 shrink-0" />}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate">{c.lastMessage}</div>
                    </div>
                    <span className="text-[10px] text-slate-300 shrink-0" style={{ color: CHANNELS[c.channel] }}>●</span>
                  </div>
                </div>
              ))
            }
          </div>
        </div>

        {/* Right: Chat */}
        <div className="flex-1 flex flex-col">
          {!detail ? <EmptyState title="Select a conversation" /> : (
            <>
              {/* Header */}
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[14px]">{detail.contact?.name || "Unknown"}</div>
                  <div className="text-[11px] text-slate-400">{detail.conversation?.channel} · {detail.contact?.phone}</div>
                </div>
                <button
                  onClick={toggleAgentMode}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${agentMode ? "bg-blue-50 text-blue-600 hover:bg-blue-100" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}
                >
                  {agentMode ? <><UserCheck size={13} /> Agent Mode</> : <><Bot size={13} /> AI Mode</>}
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-5 space-y-3 bg-slate-50/40">
                {(detail.messages || []).map((m) => (
                  <motion.div key={m.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`flex ${m.direction === "OUT" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] rounded-2xl px-3.5 py-2 text-[13.5px] ${m.direction === "OUT" ? "bg-[hsl(var(--primary))] text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                      <div>{m.text}</div>
                      <div className={`text-[10px] mt-1 flex items-center gap-1 ${m.direction === "OUT" ? "text-white/60" : "text-slate-400"}`}>
                        {m.sentById === "ai" && <><Bot size={9} /> AI · </>}
                        {fmtDate(m.createdAt)}
                      </div>
                    </div>
                  </motion.div>
                ))}
                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <div className="p-3 border-t border-slate-100 flex items-center gap-2">
                {agentMode && <span className="text-[11px] text-blue-500 font-medium px-2">Agent Mode — AI paused</span>}
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder={agentMode ? "Reply as Agent…" : `Reply on ${detail.conversation.channel}…`}
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
