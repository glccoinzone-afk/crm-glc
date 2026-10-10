import React from "react";
import { Loader2, X, Paperclip, FileText, Film, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/glc";

export const WA_GREEN = "#25D366";

export const errMsg = (e, fallback = "Something went wrong") => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
  return e?.message || fallback;
};

export const timeAgo = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
};

export const fmtDateTime = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
};

export function Card({ children, className = "", pad = true }) {
  return <div className={`bg-white rounded-2xl border border-slate-200/70 card-elev ${pad ? "p-5" : ""} ${className}`}>{children}</div>;
}

export function Btn({ children, onClick, variant = "primary", size = "md", disabled, loading, icon: Icon, className = "", type = "button", testId }) {
  const v = {
    primary: "bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90",
    green: "bg-[#25D366] text-white hover:bg-[#1fb857]",
    soft: "bg-slate-100 text-slate-700 hover:bg-slate-200",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-rose-50 text-rose-700 hover:bg-rose-100",
    outline: "border border-slate-200 text-slate-700 hover:bg-slate-50",
  }[variant];
  const s = size === "sm" ? "h-8 px-2.5 text-[12px]" : "h-10 px-3.5 text-[13px]";
  return (
    <button
      data-testid={testId}
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${s} ${v} ${className}`}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : Icon ? <Icon size={14} /> : null}
      {children}
    </button>
  );
}

export function Pill({ children, tone = "slate", className = "" }) {
  const t = {
    slate: "bg-slate-100 text-slate-600",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-rose-50 text-rose-700",
    blue: "bg-blue-50 text-blue-700",
    violet: "bg-violet-50 text-violet-700",
  }[tone];
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${t} ${className}`}>{children}</span>;
}

export const templateTone = (s) => ({ APPROVED: "green", PENDING: "amber", IN_REVIEW: "amber", REJECTED: "red", PAUSED: "amber", DISABLED: "red" }[s] || "slate");
export const campaignTone = (s) => ({ SENT: "green", SENDING: "blue", SCHEDULED: "violet", DRAFT: "slate", CANCELLED: "slate", FAILED: "red" }[s] || "slate");

export function Input({ label, hint, className = "", ...props }) {
  return (
    <label className={`block text-[12px] font-medium text-slate-600 ${className}`}>
      {label}
      <input {...props} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 bg-white text-[13px] outline-none focus:border-[hsl(var(--primary))] focus:ring-2 focus:ring-[hsl(var(--primary))]/10" />
      {hint && <span className="block mt-1 text-[11px] font-normal text-slate-400">{hint}</span>}
    </label>
  );
}

export function Textarea({ label, hint, className = "", ...props }) {
  return (
    <label className={`block text-[12px] font-medium text-slate-600 ${className}`}>
      {label}
      <textarea {...props} className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-[13px] outline-none focus:border-[hsl(var(--primary))] focus:ring-2 focus:ring-[hsl(var(--primary))]/10" />
      {hint && <span className="block mt-1 text-[11px] font-normal text-slate-400">{hint}</span>}
    </label>
  );
}

export function Select({ label, children, className = "", ...props }) {
  return (
    <label className={`block text-[12px] font-medium text-slate-600 ${className}`}>
      {label}
      <select {...props} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 bg-white text-[13px] outline-none focus:border-[hsl(var(--primary))]">
        {children}
      </select>
    </label>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="inline-flex p-1 rounded-xl bg-slate-100 gap-1">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`px-3 h-8 rounded-lg text-[12.5px] font-medium transition-colors ${value === t.key ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-800"}`}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 text-[11px] text-slate-400">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function TagChip({ children, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium">
      {children}
      {onRemove && (
        <button onClick={onRemove} className="text-slate-400 hover:text-slate-700"><X size={11} /></button>
      )}
    </span>
  );
}

/** Comma-separated tag entry that shows chips. */
export function TagInput({ value, onChange, placeholder = "Type a tag and press Enter", suggestions = [] }) {
  const [draft, setDraft] = React.useState("");
  const add = (t) => {
    const v = t.trim();
    if (v && !value.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...value, v]);
    setDraft("");
  };
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5 min-h-10 px-2 py-1.5 rounded-lg border border-slate-200 bg-white">
        {value.map((t) => <TagChip key={t} onRemove={() => onChange(value.filter((x) => x !== t))}>{t}</TagChip>)}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(draft); }
            if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
          }}
          onBlur={() => draft && add(draft)}
          placeholder={value.length ? "" : placeholder}
          className="flex-1 min-w-[120px] h-6 text-[13px] outline-none bg-transparent"
        />
      </div>
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {suggestions.filter((s) => !value.includes(s)).slice(0, 8).map((s) => (
            <button key={s} onClick={() => add(s)} className="text-[11px] px-1.5 py-0.5 rounded-md border border-dashed border-slate-300 text-slate-500 hover:border-slate-400 hover:text-slate-700">+ {s}</button>
          ))}
        </div>
      )}
    </div>
  );
}

/** WhatsApp-style bubble preview used by the template and campaign screens. */
export function PhonePreview({ header, body, footer, buttons = [], title = "GLC Zone", media }) {
  return (
    <div className="mx-auto w-[260px] rounded-[28px] border-[6px] border-slate-800 bg-slate-800 shadow-xl overflow-hidden">
      <div className="bg-[#075E54] text-white px-3 py-2 text-[12px] font-medium flex items-center gap-2">
        <span className="w-6 h-6 rounded-full bg-white/20 grid place-items-center text-[10px]">G</span>{title}
      </div>
      <div className="min-h-[220px] p-3" style={{ background: "#ECE5DD" }}>
        <div className="max-w-[92%] rounded-xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
          {media && <MediaBox media={media} />}
          {header && !media && <div className="text-[13px] font-semibold text-slate-900 mb-1">{header}</div>}
          <div className="text-[12.5px] text-slate-800 whitespace-pre-wrap break-words">{body || <span className="text-slate-400">Your message appears here</span>}</div>
          {footer && <div className="text-[10.5px] text-slate-400 mt-1.5">{footer}</div>}
          <div className="text-[9.5px] text-slate-400 text-right mt-1">10:30 ✓✓</div>
        </div>
        {buttons.filter((b) => b.text).map((b, i) => (
          <div key={i} className="max-w-[92%] mt-1 rounded-xl bg-white px-3 py-1.5 text-center text-[12px] font-medium text-[#0a7cff] shadow-sm">{b.text}</div>
        ))}
      </div>
    </div>
  );
}

export function Progress({ value, tone = "bg-[#25D366]" }) {
  return (
    <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);

const FMT_ICON = { IMAGE: ImageIcon, VIDEO: Film, DOCUMENT: FileText };
export const MEDIA_ACCEPT = { IMAGE: ".jpg,.jpeg,.png", VIDEO: ".mp4,.3gp", DOCUMENT: ".pdf", ANY: ".jpg,.jpeg,.png,.mp4,.3gp,.pdf" };

/** Image/video/document block shown inside a WhatsApp bubble. media: {format, url?, name?} */
export function MediaBox({ media }) {
  const Icon = FMT_ICON[media.format] || FileText;
  if (media.format === "IMAGE" && media.url) return <img src={media.url} alt="" className="rounded-lg mb-1.5 w-full max-h-40 object-cover" />;
  if (media.format === "VIDEO" && media.url) return <video src={media.url} className="rounded-lg mb-1.5 w-full max-h-40 bg-black" muted />;
  return (
    <div className="rounded-lg mb-1.5 bg-slate-100 h-20 grid place-items-center text-slate-500 text-[11px]">
      <div className="flex flex-col items-center gap-1"><Icon size={20} />{media.name || media.format.toLowerCase()}</div>
    </div>
  );
}

/** Uploads one file to the CRM and reports the stored media record. `format` limits what can be chosen (IMAGE | VIDEO | DOCUMENT | ANY). */
export function MediaPicker({ format = "ANY", value, onChange, label = "Attach file" }) {
  const [busy, setBusy] = React.useState(false);
  const ref = React.useRef(null);
  const pick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/ocm/wa/media", fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (format !== "ANY" && data.format !== format) throw new Error(`Please choose a ${format.toLowerCase()} file`);
      onChange({ ...data, url: URL.createObjectURL(file) });
    } catch (err) {
      toast.error(err?.response?.data?.detail || err.message || "Upload failed");
    } finally { setBusy(false); }
  };
  return (
    <div>
      <input ref={ref} type="file" accept={MEDIA_ACCEPT[format]} onChange={pick} className="hidden" />
      {value ? (
        <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="w-10 h-10 rounded-md overflow-hidden bg-slate-200 grid place-items-center shrink-0">
            {value.format === "IMAGE" && value.url ? <img src={value.url} alt="" className="w-full h-full object-cover" /> : React.createElement(FMT_ICON[value.format] || FileText, { size: 18, className: "text-slate-500" })}
          </div>
          <div className="min-w-0 flex-1"><div className="text-[12.5px] font-medium text-slate-800 truncate">{value.filename || value.name}</div><div className="text-[11px] text-slate-400">{value.format.toLowerCase()}{value.size ? ` · ${(value.size / 1024 / 1024).toFixed(1)} MB` : ""}</div></div>
          <button onClick={() => onChange(null)} className="text-slate-400 hover:text-rose-600"><X size={15} /></button>
        </div>
      ) : (
        <button type="button" onClick={() => ref.current?.click()} disabled={busy} className="w-full h-10 rounded-lg border border-dashed border-slate-300 text-[13px] text-slate-600 hover:border-slate-400 hover:bg-slate-50 inline-flex items-center justify-center gap-2 disabled:opacity-60">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} />} {label}
        </button>
      )}
      <div className="text-[11px] text-slate-400 mt-1">{format === "ANY" ? "JPG/PNG up to 5 MB, MP4 or PDF up to 16 MB" : format === "IMAGE" ? "JPG or PNG, up to 5 MB" : format === "VIDEO" ? "MP4, up to 16 MB" : "PDF, up to 16 MB"}</div>
    </div>
  );
}
