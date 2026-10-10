import React, { useEffect, useState } from "react";
import { Link2, Copy, Trash2, MousePointerClick } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/glc";
import { PageHeader, EmptyState } from "@/components/common/GlcUI";
import { Card, Btn, Input, errMsg, fmtDateTime } from "./ui";

export default function WaLinks() {
  const [rows, setRows] = useState([]);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/ocm/links").then((r) => setRows(r.data.items || []));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/ocm/links", { url, name });
      setUrl(""); setName("");
      navigator.clipboard?.writeText(data.shortUrl);
      toast.success("Short link created and copied");
      load();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const copy = (t) => { navigator.clipboard?.writeText(t); toast.success("Copied"); };

  return (
    <div className="space-y-6">
      <PageHeader testId="wa-links" title="Short links" subtitle="Put a tracked link in a campaign and see how many people tapped it" />
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_240px_auto] gap-3 items-end">
          <Input label="Destination link" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://glczone.in/product/…" />
          <Input label="Label (optional)" value={name} onChange={(e) => setName(e.target.value)} placeholder="Diwali banner" />
          <Btn variant="green" icon={Link2} onClick={create} loading={busy} disabled={!url}>Create link</Btn>
        </div>
      </Card>
      {rows.length === 0 ? <EmptyState icon={Link2} title="No links yet" /> : (
        <Card pad={false}>
          <div className="divide-y divide-slate-100">
            {rows.map((l) => (
              <div key={l.id} className="px-5 py-3.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium text-slate-900 truncate">{l.name}</div>
                  <div className="text-[12px] text-[hsl(var(--primary))] font-mono truncate">{l.shortUrl}</div>
                  <div className="text-[11.5px] text-slate-400 truncate">{l.url}</div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right"><div className="flex items-center gap-1 text-[18px] font-semibold tabular"><MousePointerClick size={14} className="text-slate-400" />{l.clicks}</div><div className="text-[10.5px] text-slate-400">{l.lastClickAt ? `last ${fmtDateTime(l.lastClickAt)}` : "no clicks yet"}</div></div>
                  <Btn size="sm" variant="soft" icon={Copy} onClick={() => copy(l.shortUrl)}>Copy</Btn>
                  <button onClick={async () => { await api.delete(`/ocm/links/${l.id}`); load(); }} className="text-slate-400 hover:text-rose-600"><Trash2 size={15} /></button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
