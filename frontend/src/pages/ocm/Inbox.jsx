import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send, Search, Bot, UserCheck, StickyNote, Zap, AlertTriangle, Check, CheckCheck, MessageSquare, X } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/glc";
import { useAuth } from "@/context/AuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Btn, Pill, Select, Tabs, TagChip, errMsg, timeAgo, fmtDateTime } from "./wa/ui";

const CHANNELS = { TELEGRAM: "#0088CC", WHATSAPP: "#25D366", INSTAGRAM: "#E1306C", FACEBOOK: "#1877F2", WEBCHAT: "#064E3B" };
const WINDOW_MS = 24 * 3600 * 1000;

function Ticks({ status }) {
  if (status === "FAILED") return <span className="text-rose-300" title="Failed">!</span>;
  if (status === "READ") return <CheckCheck size={12} className="text-sky-300" />;
  if (status === "DELIVERED") return <CheckCheck size={12} />;
  return <Check size={12} />;
}

export default function Inbox() {
  const { user } = useAuth();
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [notes, setNotes] = useState([]);
  const [agents, setAgents] = useState([]);
  const [canned, setCanned] = useState([]);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [tab, setTab] = useState("all");
  const [channel, setChannel] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState("info");
  const bottomRef = useRef(null);

  const loadList = useCallback(() => {
    api.get("/ocm/conversations", { params: channel ? { channel } : {} })
      .then((r) => { const items = r.data.items || []; setConvs(items); setSelected((s) => s || items[0]?.id || null); })
      .finally(() => setLoading(false));
  }, [channel]);
  useEffect(() => { loadList(); const t = setInterval(loadList, 6000); return () => clearInterval(t); }, [loadList]);
  useEffect(() => {
    api.get("/ocm/agents").then((r) => setAgents(r.data.items || [])).catch(() => {});
    api.get("/ocm/canned").then((r) => setCanned(r.data.items || [])).catch(() => {});
  }, []);

  const loadDetail = useCallback((id, scroll) => {
    api.get(`/ocm/conversations/${id}`).then((r) => {
      setDetail(r.data);
      if (scroll) setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 60);
    });
    api.get(`/ocm/conversations/${id}/notes`).then((r) => setNotes(r.data.items || [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (!selected) return undefined;
    loadDetail(selected, true);
    api.post(`/ocm/conversations/${selected}/read`).catch(() => {});
    const t = setInterval(() => loadDetail(selected, false), 4000);
    return () => clearInterval(t);
  }, [selected, loadDetail]);

  const list = useMemo(() => convs.filter((c) => {
    if (q && !(c.contactName || "").toLowerCase().includes(q.toLowerCase()) && !(c.lastMessage || "").toLowerCase().includes(q.toLowerCase())) return false;
    if (tab === "mine") return c.assignedTo === user?.id;
    if (tab === "unassigned") return !c.assignedTo;
    if (tab === "unread") return (c.unread || 0) > 0;
    return true;
  }), [convs, q, tab, user]);
  const unreadTotal = convs.reduce((a, c) => a + (c.unread || 0), 0);

  const conv = detail?.conversation;
  const lastIn = [...(detail?.messages || [])].reverse().find((m) => m.direction === "IN");
  const windowClosed = conv?.channel === "WHATSAPP" && (!lastIn || Date.now() - new Date(lastIn.createdAt).getTime() > WINDOW_MS);

  const send = async (override) => {
    const t = (override ?? text).trim();
    if (!t || !selected) return;
    setText("");
    try {
      await api.post(`/ocm/conversations/${selected}/messages`, { text: t, direction: "OUT", channel: conv?.channel });
      loadDetail(selected, true);
      loadList();
    } catch (e) { toast.error(errMsg(e)); setText(t); }
  };
  const patch = async (body) => { await api.put(`/ocm/conversations/${selected}`, body); loadDetail(selected, false); loadList(); };
  const assign = async (agentId) => { await api.post(`/ocm/conversations/${selected}/assign`, { agentId: agentId || null }); loadDetail(selected, false); loadList(); };
  const addNote = async () => { if (!note.trim()) return; await api.post(`/ocm/conversations/${selected}/notes`, { text: note }); setNote(""); loadDetail(selected, false); };

  const slash = text.startsWith("/") ? canned.filter((c) => (c.shortcut || c.title).toLowerCase().includes(text.slice(1).toLowerCase())) : [];
  const days = useMemo(() => {
    const out = []; let last = "";
    (detail?.messages || []).forEach((m) => {
      const d = new Date(m.createdAt).toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" });
      if (d !== last) { out.push({ divider: d, id: `d-${d}` }); last = d; }
      out.push(m);
    });
    return out;
  }, [detail]);

  return (
    <div data-testid="inbox-page" className="flex h-[calc(100vh-110px)] rounded-2xl border border-slate-200 overflow-hidden bg-white card-elev">
      {/* conversation list */}
      <div className="w-[320px] border-r border-slate-100 flex flex-col shrink-0">
        <div className="p-3 space-y-2.5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <h1 className="text-[16px] font-semibold text-slate-900">Inbox {unreadTotal > 0 && <span className="ml-1 text-[11px] px-1.5 py-0.5 rounded-full bg-[#25D366] text-white">{unreadTotal}</span>}</h1>
            <select value={channel} onChange={(e) => setChannel(e.target.value)} className="h-8 px-2 rounded-lg border border-slate-200 text-[12px] outline-none">
              <option value="">All channels</option>
              {Object.keys(CHANNELS).map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="relative"><Search size={14} className="absolute left-3 top-2.5 text-slate-400" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search chats" className="w-full h-9 pl-9 pr-3 rounded-lg bg-slate-100 text-[13px] outline-none" /></div>
          <Tabs value={tab} onChange={setTab} tabs={[{ key: "all", label: "All" }, { key: "mine", label: "Mine" }, { key: "unassigned", label: "Open" }, { key: "unread", label: "Unread" }]} />
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? <div className="p-6 text-center text-[13px] text-slate-400">Loading…</div> : list.length === 0 ? (
            <div className="p-10 text-center text-[13px] text-slate-400"><MessageSquare className="mx-auto mb-2" size={22} />No conversations here</div>
          ) : list.map((c) => (
            <button key={c.id} onClick={() => setSelected(c.id)} className={`w-full text-left px-3 py-3 flex gap-3 border-b border-slate-50 hover:bg-slate-50 ${selected === c.id ? "bg-slate-100/80" : ""}`}>
              <div className="relative">
                <Avatar className="h-10 w-10"><AvatarFallback className="text-[13px] bg-slate-200">{(c.contactName || "?")[0]}</AvatarFallback></Avatar>
                <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white" style={{ background: CHANNELS[c.channel] || "#94A3B8" }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[13.5px] truncate ${c.unread ? "font-semibold text-slate-900" : "font-medium text-slate-800"}`}>{c.contactName || "Unknown"}</span>
                  <span className="text-[10.5px] text-slate-400 shrink-0">{timeAgo(c.lastMessageAt)}</span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5">
                  <span className={`text-[12px] truncate ${c.unread ? "text-slate-700" : "text-slate-400"}`}>{c.lastMessage}</span>
                  {c.unread > 0 && <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-[#25D366] text-white text-[10.5px] font-semibold grid place-items-center">{c.unread}</span>}
                </div>
                {(c.assignedName || c.agentMode) && <div className="mt-1 flex gap-1">{c.assignedName && <Pill tone="blue">{c.assignedName}</Pill>}{c.agentMode && <Pill tone="violet">Human</Pill>}</div>}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* chat */}
      <div className="flex-1 flex flex-col min-w-0">
        {!detail ? <div className="flex-1 grid place-items-center text-[13px] text-slate-400">Select a conversation</div> : (
          <>
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-semibold text-[14.5px] text-slate-900 truncate">{detail.contact?.name || "Unknown"}</div>
                <div className="text-[11.5px] text-slate-500"><span style={{ color: CHANNELS[conv.channel] }}>●</span> {conv.channel} · {detail.contact?.phone}</div>
              </div>
              <div className="flex items-center gap-2">
                <Btn size="sm" variant={conv.agentMode ? "soft" : "outline"} icon={conv.agentMode ? UserCheck : Bot} onClick={() => patch({ agentMode: !conv.agentMode })}>{conv.agentMode ? "Human replying" : "Bot active"}</Btn>
                <Btn size="sm" variant="outline" onClick={() => patch({ status: conv.status === "CLOSED" ? "OPEN" : "CLOSED" })}>{conv.status === "CLOSED" ? "Reopen" : "Resolve"}</Btn>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2" style={{ background: "#F6F5F1" }}>
              {days.map((m) => m.divider ? (
                <div key={m.id} className="flex justify-center"><span className="text-[11px] px-2.5 py-1 rounded-full bg-white/80 text-slate-500 shadow-sm">{m.divider}</span></div>
              ) : (
                <div key={m.id} className={`flex ${m.direction === "OUT" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[68%] rounded-2xl px-3.5 py-2 text-[13.5px] shadow-sm ${m.direction === "OUT" ? "bg-[hsl(var(--primary))] text-white rounded-br-md" : "bg-white text-slate-800 rounded-bl-md"}`}>
                    <div className="whitespace-pre-wrap break-words">{m.text}</div>
                    <div className={`text-[10px] mt-1 flex items-center justify-end gap-1 ${m.direction === "OUT" ? "text-white/60" : "text-slate-400"}`}>
                      {m.sentById === "ai" && <Bot size={9} />}{m.sentBy && m.direction === "OUT" && <span>{m.sentBy} ·</span>}
                      {new Date(m.createdAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      {m.direction === "OUT" && <Ticks status={m.status} />}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {windowClosed && (
              <div className="px-5 py-2 bg-amber-50 border-t border-amber-100 text-[12px] text-amber-800 flex items-center gap-2">
                <AlertTriangle size={13} /> The 24-hour reply window is closed. WhatsApp only delivers approved templates until the customer writes again; send one from Campaigns.
              </div>
            )}
            <div className="relative p-3 border-t border-slate-100">
              {slash.length > 0 && (
                <div className="absolute bottom-full left-3 right-3 mb-1 max-h-48 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                  {slash.map((c) => (
                    <button key={c.id} onClick={() => setText(c.text)} className="w-full text-left px-3 py-2 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                      <div className="text-[12.5px] font-medium text-slate-800">/{c.shortcut || c.title}</div>
                      <div className="text-[11.5px] text-slate-500 truncate">{c.text}</div>
                    </button>
                  ))}
                </div>
              )}
              <div className="flex items-end gap-2">
                <textarea
                  rows={1}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                  placeholder={`Reply on ${conv.channel}…   (type / for saved replies)`}
                  className="flex-1 max-h-32 min-h-10 px-3 py-2 rounded-xl border border-slate-200 text-[13.5px] outline-none focus:border-[hsl(var(--primary))] resize-none"
                  data-testid="chat-input"
                />
                <Btn variant="green" icon={Send} onClick={() => send()} testId="chat-send">Send</Btn>
              </div>
            </div>
          </>
        )}
      </div>

      {/* side panel */}
      {detail && (
        <div className="w-[290px] border-l border-slate-100 hidden xl:flex flex-col shrink-0">
          <div className="p-3 border-b border-slate-100"><Tabs value={panel} onChange={setPanel} tabs={[{ key: "info", label: "Details" }, { key: "notes", label: "Notes", count: notes.length }, { key: "quick", label: "Replies" }]} /></div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {panel === "info" && (
              <>
                <div className="text-center">
                  <Avatar className="h-14 w-14 mx-auto"><AvatarFallback className="text-lg bg-slate-200">{(detail.contact?.name || "?")[0]}</AvatarFallback></Avatar>
                  <div className="mt-2 font-semibold text-slate-900">{detail.contact?.name}</div>
                  <div className="text-[12px] text-slate-500 font-mono">{detail.contact?.phone}</div>
                  <div className="text-[12px] text-slate-500">{detail.contact?.email}</div>
                </div>
                <Select label="Assigned to" value={conv.assignedTo || ""} onChange={(e) => assign(e.target.value)}>
                  <option value="">Unassigned</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </Select>
                <div>
                  <div className="text-[12px] font-medium text-slate-600 mb-1.5">Tags</div>
                  <div className="flex flex-wrap gap-1">{(detail.contact?.tags || []).map((t) => <TagChip key={t}>{t}</TagChip>)}{!(detail.contact?.tags || []).length && <span className="text-[12px] text-slate-400">No tags</span>}</div>
                </div>
                <dl className="text-[12px] space-y-1.5 text-slate-600">
                  <div className="flex justify-between"><dt>Status</dt><dd><Pill tone={conv.status === "CLOSED" ? "slate" : "green"}>{conv.status}</Pill></dd></div>
                  <div className="flex justify-between"><dt>Language</dt><dd>{detail.contact?.preferredLang || "—"}</dd></div>
                  <div className="flex justify-between"><dt>Subscribed</dt><dd>{detail.contact?.optedOut || detail.contact?.subscribed === false ? "No" : "Yes"}</dd></div>
                </dl>
              </>
            )}
            {panel === "notes" && (
              <>
                <div className="space-y-2">
                  {notes.length === 0 && <div className="text-[12.5px] text-slate-400">Private notes only your team can see.</div>}
                  {notes.map((n) => (
                    <div key={n.id} className="rounded-xl bg-amber-50 border border-amber-100 p-3">
                      <div className="text-[12.5px] text-slate-800 whitespace-pre-wrap">{n.text}</div>
                      <div className="text-[10.5px] text-slate-500 mt-1">{n.by} · {fmtDateTime(n.createdAt)}</div>
                    </div>
                  ))}
                </div>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Add an internal note" className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[13px] outline-none focus:border-[hsl(var(--primary))]" />
                <Btn size="sm" variant="soft" icon={StickyNote} onClick={addNote} disabled={!note.trim()}>Save note</Btn>
              </>
            )}
            {panel === "quick" && <CannedPanel canned={canned} reload={() => api.get("/ocm/canned").then((r) => setCanned(r.data.items || []))} use={(t) => setText(t)} />}
          </div>
        </div>
      )}
    </div>
  );
}

function CannedPanel({ canned, reload, use }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const add = async () => {
    try { await api.post("/ocm/canned", { title, text: body, shortcut: title.toLowerCase().replace(/\s+/g, "-") }); setTitle(""); setBody(""); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <div className="space-y-2">
        {canned.length === 0 && <div className="text-[12.5px] text-slate-400">Save replies you send often. Type / in the message box to use them.</div>}
        {canned.map((c) => (
          <div key={c.id} className="rounded-xl border border-slate-200 p-2.5">
            <div className="flex items-center justify-between"><span className="text-[12.5px] font-medium text-slate-800 flex items-center gap-1"><Zap size={11} className="text-amber-500" />{c.title}</span>
              <button onClick={async () => { await api.delete(`/ocm/canned/${c.id}`); reload(); }} className="text-slate-300 hover:text-rose-600"><X size={13} /></button></div>
            <div className="text-[12px] text-slate-500 line-clamp-2 mt-0.5">{c.text}</div>
            <button onClick={() => use(c.text)} className="text-[11.5px] font-medium text-[hsl(var(--primary))] mt-1">Use</button>
          </div>
        ))}
      </div>
      <div className="space-y-2 border-t border-slate-100 pt-3">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (e.g. Delivery time)" className="w-full h-9 px-3 rounded-lg border border-slate-200 text-[13px] outline-none" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} placeholder="Reply text" className="w-full px-3 py-2 rounded-lg border border-slate-200 text-[13px] outline-none" />
        <Btn size="sm" variant="soft" onClick={add} disabled={!title || !body}>Save reply</Btn>
      </div>
    </>
  );
}
