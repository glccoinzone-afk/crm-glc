import React, { useEffect, useState } from "react";
import { MessageSquare, Users, Clock, Inbox as InboxIcon } from "lucide-react";
import api, { fmtNum } from "@/lib/glc";
import { PageHeader, StatCard } from "@/components/common/GlcUI";
import { Card, Tabs } from "./wa/ui";

const COLORS = { WHATSAPP: "#25D366", TELEGRAM: "#0088CC", FACEBOOK: "#1877F2", INSTAGRAM: "#E1306C", WEBCHAT: "#064E3B" };

export default function Reports() {
  const [days, setDays] = useState("30");
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); api.get("/ocm/reports", { params: { days } }).then((r) => setD(r.data)).catch(() => setD({ error: true })); }, [days]);

  const totalIn = d?.channels?.reduce((a, c) => a + c.in, 0) || 0;
  const totalOut = d?.channels?.reduce((a, c) => a + c.out, 0) || 0;
  const maxDay = Math.max(1, ...(d?.daily || []).map((x) => x.in + x.out));
  const maxCh = Math.max(1, ...(d?.channels || []).map((c) => c.in + c.out));
  const open = (d?.conversations?.OPEN || 0) + (d?.conversations?.IN_PROGRESS || 0);

  return (
    <div className="space-y-6">
      <PageHeader testId="ocm-reports" title="Reports" subtitle="How your conversations are going across every channel" actions={
        <Tabs value={days} onChange={setDays} tabs={[{ key: "7", label: "7 days" }, { key: "30", label: "30 days" }, { key: "90", label: "90 days" }]} />
      } />
      {!d ? <div className="text-center text-[13px] text-slate-400 py-20">Loading…</div> : d.error ? <div className="text-center text-[13px] text-rose-600 py-20">Could not load the report.</div> : (
        <>
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard label="Messages received" value={fmtNum(totalIn)} change={`${fmtNum(totalOut)} sent by you or the bot`} icon={MessageSquare} tone="primary" />
            <StatCard label="New contacts" value={fmtNum(d.newContacts)} change={`${fmtNum(d.contacts)} in total`} icon={Users} tone="success" />
            <StatCard label="Open chats" value={fmtNum(open)} change={`${fmtNum(d.conversations?.CLOSED || 0)} resolved`} icon={InboxIcon} tone="warn" />
            <StatCard label="Median first reply" value={d.medianFirstReplyMinutes === null ? "—" : `${d.medianFirstReplyMinutes} min`} change="Recent conversations" icon={Clock} tone="accent" />
          </div>

          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[14px] font-semibold text-slate-900">Messages per day</h3>
              <div className="flex items-center gap-3 text-[11.5px] text-slate-500"><span className="flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-[#25D366]" /> Received</span><span className="flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-slate-300" /> Sent</span></div>
            </div>
            <div className="flex items-end gap-[3px] h-40">
              {d.daily.map((x) => (
                <div key={x.date} className="flex-1 flex flex-col justify-end h-full group relative" title={`${x.date}: ${x.in} received, ${x.out} sent`}>
                  <div className="w-full bg-slate-300 rounded-t-sm" style={{ height: `${(x.out / maxDay) * 100}%` }} />
                  <div className="w-full bg-[#25D366]" style={{ height: `${(x.in / maxDay) * 100}%` }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[11px] text-slate-400 mt-2"><span>{d.daily[0]?.date}</span><span>{d.daily[d.daily.length - 1]?.date}</span></div>
          </Card>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Card>
              <h3 className="text-[14px] font-semibold text-slate-900 mb-4">By channel</h3>
              {d.channels.length === 0 ? <div className="text-[13px] text-slate-400">No messages in this period.</div> : (
                <div className="space-y-3">
                  {d.channels.map((c) => (
                    <div key={c.key}>
                      <div className="flex justify-between text-[12.5px] mb-1"><span className="font-medium text-slate-800">{c.label}</span><span className="text-slate-500 tabular">{fmtNum(c.in)} in · {fmtNum(c.out)} out</span></div>
                      <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${((c.in + c.out) / maxCh) * 100}%`, background: COLORS[c.key] || "#94A3B8" }} /></div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
            <Card>
              <h3 className="text-[14px] font-semibold text-slate-900 mb-4">Social posts</h3>
              {Object.keys(d.posts || {}).length === 0 ? <div className="text-[13px] text-slate-400">No posts yet. Plan one in the Social Scheduler.</div> : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(d.posts).map(([k, v]) => <div key={k} className="rounded-xl bg-slate-50 py-3 text-center"><div className="text-[20px] font-semibold tabular">{v}</div><div className="text-[11px] uppercase tracking-wide text-slate-500">{k.replace(/_/g, " ")}</div></div>)}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
