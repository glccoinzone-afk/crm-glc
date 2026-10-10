import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Users, Send, CheckCheck, Eye, AlertTriangle, FileText, Megaphone, Link2, Upload, ShieldCheck, Settings2, Check } from "lucide-react";
import { toast } from "sonner";
import api, { fmtNum } from "@/lib/glc";
import { PageHeader } from "@/components/common/GlcUI";
import { Card, Btn, Pill, Input, Progress, pct, errMsg, campaignTone, fmtDateTime } from "./ui";

function Stat({ icon: Icon, label, value, sub, tone = "text-slate-700 bg-slate-100" }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-[0.08em] font-semibold text-slate-500">{label}</div>
        <div className={`w-8 h-8 rounded-lg grid place-items-center ${tone}`}><Icon size={15} /></div>
      </div>
      <div className="mt-3 text-[26px] font-semibold tracking-tight tabular text-slate-900">{value}</div>
      {sub && <div className="text-[11.5px] text-slate-500 mt-1">{sub}</div>}
    </Card>
  );
}

function SetupCard({ settings, reload }) {
  const [waba, setWaba] = useState(settings?.wabaId || "");
  const [saving, setSaving] = useState(false);
  useEffect(() => setWaba(settings?.wabaId || ""), [settings?.wabaId]);
  const save = async () => {
    setSaving(true);
    try {
      await api.put("/ocm/wa/settings", { wabaId: waba });
      toast.success("Saved");
      reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const phone = settings?.phone;
  const waCheck = settings?.waba;
  const steps = [
    { ok: settings?.tokenSet, label: "Access token on the server", help: "Set WHATSAPP_ACCESS_TOKEN in the backend .env" },
    { ok: !!settings?.phoneId && phone && !phone.error, label: phone?.display_phone_number ? `Number ${phone.display_phone_number} (${phone.verified_name || "unnamed"})` : "Phone number connected", help: phone?.error || "Set WHATSAPP_PHONE_NUMBER_ID in the backend .env" },
    { ok: !!settings?.wabaId && waCheck && !waCheck.error, label: waCheck?.name ? `Business account ${waCheck.name}` : "WhatsApp Business Account ID", help: waCheck?.error || "Paste the Account ID from WhatsApp Manager below" },
    { ok: settings?.verifyTokenSet, label: "Webhook verify token", help: "Set WHATSAPP_VERIFY_TOKEN, then use /api/webhooks/whatsapp as the callback URL in Meta" },
  ];
  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Settings2 size={16} className="text-slate-500" />
        <h3 className="text-[14px] font-semibold text-slate-900">WhatsApp connection</h3>
      </div>
      <ul className="space-y-2.5">
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <span className={`mt-0.5 w-5 h-5 rounded-full grid place-items-center shrink-0 ${s.ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
              {s.ok ? <Check size={12} /> : <AlertTriangle size={11} />}
            </span>
            <div>
              <div className="text-[13px] text-slate-800">{s.label}</div>
              {!s.ok && <div className="text-[11.5px] text-slate-500 break-words">{s.help}</div>}
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-end gap-2">
        <Input className="flex-1" label="WhatsApp Business Account ID" value={waba} onChange={(e) => setWaba(e.target.value)} placeholder="e.g. 1234567890123456" hint="WhatsApp Manager → Phone numbers → the number after asset_id= in the address bar" />
        <Btn onClick={save} loading={saving} variant="soft">Save</Btn>
      </div>
    </Card>
  );
}

export default function WaOverview() {
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const load = () => {
    api.get("/ocm/wa/stats").then((r) => setStats(r.data)).catch(() => {});
    api.get("/ocm/wa/settings").then((r) => setSettings(r.data)).catch(() => {});
    api.get("/ocm/wa/campaigns").then((r) => setCampaigns((r.data.items || []).slice(0, 5))).catch(() => {});
  };
  useEffect(load, []);
  const m = stats?.messages || {};
  const tpl = stats?.templates || {};

  return (
    <div className="space-y-6">
      <PageHeader testId="wa-overview" title="WhatsApp" subtitle="Templates, campaigns and customer conversations in one place" actions={
        <>
          <Link to="/ocm/contacts"><Btn variant="outline" icon={Upload}>Import contacts</Btn></Link>
          <Link to="/ocm/campaigns"><Btn variant="green" icon={Megaphone}>New campaign</Btn></Link>
        </>
      } />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <Stat icon={Users} label="Reachable contacts" value={fmtNum(stats?.subscribed)} sub={`${fmtNum(stats?.optedOut)} opted out · ${fmtNum(stats?.contacts)} total`} tone="text-emerald-700 bg-emerald-50" />
        <Stat icon={Send} label="Messages sent" value={fmtNum(m.sent)} sub={`${campaignsLine(stats)}`} tone="text-blue-700 bg-blue-50" />
        <Stat icon={CheckCheck} label="Delivered" value={`${pct(m.delivered, m.sent)}%`} sub={`${fmtNum(m.delivered)} of ${fmtNum(m.sent)}`} tone="text-indigo-700 bg-indigo-50" />
        <Stat icon={Eye} label="Read" value={`${pct(m.read, m.sent)}%`} sub={`${fmtNum(m.failed)} failed`} tone="text-violet-700 bg-violet-50" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 space-y-4">
          <Card pad={false}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h3 className="text-[14px] font-semibold text-slate-900">Recent campaigns</h3>
              <Link to="/ocm/campaigns" className="text-[12px] font-medium text-[hsl(var(--primary))] hover:underline">View all</Link>
            </div>
            {campaigns.length === 0 ? (
              <div className="p-10 text-center text-[13px] text-slate-500">No campaigns yet. Create a template first, then send it to a segment.</div>
            ) : campaigns.map((c) => (
              <div key={c.id} className="px-5 py-3.5 border-b border-slate-50 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[13.5px] font-medium text-slate-900 truncate">{c.name}</div>
                    <div className="text-[11.5px] text-slate-500">{c.templateName} · {fmtDateTime(c.scheduledAt || c.createdAt)}</div>
                  </div>
                  <Pill tone={campaignTone(c.status)}>{c.status}</Pill>
                </div>
                {c.stats?.total > 0 && (
                  <div className="mt-2.5">
                    <Progress value={pct(c.stats.read, c.stats.total)} />
                    <div className="mt-1 text-[11px] text-slate-500">{c.stats.total} sent · {pct(c.stats.delivered, c.stats.total)}% delivered · {pct(c.stats.read, c.stats.total)}% read · {c.stats.failed} failed</div>
                  </div>
                )}
              </div>
            ))}
          </Card>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { to: "/ocm/templates", icon: FileText, title: "Templates", text: `${tpl.APPROVED || 0} approved · ${(tpl.PENDING || 0) + (tpl.IN_REVIEW || 0)} in review` },
              { to: "/ocm/inbox", icon: MessageCircle, title: "Inbox", text: "Reply to customers, assign chats" },
              { to: "/ocm/links", icon: Link2, title: "Short links", text: `${fmtNum(stats?.linkClicks)} clicks tracked` },
            ].map((x) => (
              <Link key={x.to} to={x.to}>
                <Card className="hover:border-slate-300 transition-colors h-full">
                  <x.icon size={18} className="text-[hsl(var(--primary))]" />
                  <div className="mt-2 text-[14px] font-semibold text-slate-900">{x.title}</div>
                  <div className="text-[12px] text-slate-500 mt-0.5">{x.text}</div>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <SetupCard settings={settings} reload={load} />
          <Card>
            <div className="flex items-center gap-2 mb-2"><ShieldCheck size={16} className="text-slate-500" /><h3 className="text-[14px] font-semibold text-slate-900">Good practice</h3></div>
            <ul className="text-[12.5px] text-slate-600 space-y-1.5 list-disc pl-4">
              <li>Send marketing templates only to contacts who agreed to receive them.</li>
              <li>Customers who reply STOP are removed from every future campaign automatically.</li>
              <li>Keep one clear message per campaign; many failures hurt your quality rating.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

function campaignsLine(stats) {
  if (!stats) return "";
  return `${stats.campaigns || 0} campaigns · ${stats.scheduled || 0} scheduled`;
}
