import React from "react";
import { motion } from "framer-motion";

export function PageHeader({ title, subtitle, actions, testId = "page-header" }) {
  return (
    <div data-testid={testId} className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6 pb-5 border-b border-slate-200/70">
      <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-[22px] md:text-[26px] font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="text-[13px] text-slate-500 mt-1">{subtitle}</p>}
      </motion.div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, change, icon: Icon, tone = "primary", testId }) {
  const tones = {
    primary: "bg-[hsl(158_64%_96%)] text-[hsl(var(--primary))]",
    accent: "bg-[hsl(27_100%_96%)] text-[hsl(var(--accent))]",
    success: "bg-emerald-50 text-emerald-700",
    warn: "bg-amber-50 text-amber-700",
    danger: "bg-rose-50 text-rose-700",
    slate: "bg-slate-100 text-slate-700",
  };
  return (
    <motion.div
      data-testid={testId}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden bg-white rounded-2xl border border-slate-200/70 p-5 card-elev hover:-translate-y-0.5 transition-transform"
    >
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-[0.08em] font-semibold text-slate-500">{label}</div>
        {Icon && (
          <div className={`w-8 h-8 rounded-lg grid place-items-center ${tones[tone]}`}>
            <Icon size={15} strokeWidth={1.75} />
          </div>
        )}
      </div>
      <div className="mt-3 text-[26px] font-semibold tracking-tight tabular text-slate-900">{value}</div>
      {change && <div className="text-[11.5px] text-slate-500 mt-1">{change}</div>}
    </motion.div>
  );
}

export function EmptyState({ title, description, icon: Icon, action, testId = "empty-state" }) {
  return (
    <div data-testid={testId} className="bg-white rounded-2xl border border-dashed border-slate-200 p-12 text-center">
      {Icon && (
        <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-50 grid place-items-center mb-4">
          <Icon size={22} className="text-slate-400" strokeWidth={1.5} />
        </div>
      )}
      <div className="text-[15px] font-semibold text-slate-900">{title}</div>
      {description && <div className="text-[13px] text-slate-500 mt-1 max-w-md mx-auto">{description}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

const statusStyles = {
  NEW: "bg-blue-50 text-blue-700",
  CONTACTED: "bg-cyan-50 text-cyan-700",
  QUALIFIED: "bg-indigo-50 text-indigo-700",
  PROPOSAL: "bg-violet-50 text-violet-700",
  NEGOTIATION: "bg-amber-50 text-amber-700",
  WON: "bg-emerald-50 text-emerald-700",
  LOST: "bg-rose-50 text-rose-700",
  PENDING: "bg-amber-50 text-amber-700",
  CONFIRMED: "bg-blue-50 text-blue-700",
  PROCESSING: "bg-indigo-50 text-indigo-700",
  SHIPPED: "bg-violet-50 text-violet-700",
  DELIVERED: "bg-emerald-50 text-emerald-700",
  CANCELLED: "bg-slate-100 text-slate-600",
  UNPAID: "bg-rose-50 text-rose-700",
  PARTIAL: "bg-amber-50 text-amber-700",
  PAID: "bg-emerald-50 text-emerald-700",
  DRAFT: "bg-slate-100 text-slate-600",
  ACTIVE: "bg-emerald-50 text-emerald-700",
  ON_HOLD: "bg-amber-50 text-amber-700",
  COMPLETED: "bg-slate-100 text-slate-700",
  APPROVED: "bg-emerald-50 text-emerald-700",
  REJECTED: "bg-rose-50 text-rose-700",
  OPEN: "bg-blue-50 text-blue-700",
  IN_PROGRESS: "bg-indigo-50 text-indigo-700",
  RESOLVED: "bg-emerald-50 text-emerald-700",
  CLOSED: "bg-slate-100 text-slate-600",
  TODO: "bg-slate-100 text-slate-700",
  REVIEW: "bg-amber-50 text-amber-700",
  DONE: "bg-emerald-50 text-emerald-700",
  LOW: "bg-slate-100 text-slate-700",
  MEDIUM: "bg-blue-50 text-blue-700",
  HIGH: "bg-amber-50 text-amber-700",
  URGENT: "bg-rose-50 text-rose-700",
  PRESENT: "bg-emerald-50 text-emerald-700",
  ABSENT: "bg-rose-50 text-rose-700",
  HALF_DAY: "bg-amber-50 text-amber-700",
  LATE: "bg-orange-50 text-orange-700",
  ASSIGNED: "bg-blue-50 text-blue-700",
  IN_TRANSIT: "bg-indigo-50 text-indigo-700",
  FAILED: "bg-rose-50 text-rose-700",
  CONVERTED: "bg-emerald-50 text-emerald-700",
  GENERATED: "bg-emerald-50 text-emerald-700",
  CREDITED: "bg-violet-50 text-violet-700",
  CANCELLED: "bg-slate-100 text-slate-500",
};

export function StatusBadge({ value, testId }) {
  const cls = statusStyles[value] || "bg-slate-100 text-slate-600";
  return (
    <span data-testid={testId} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {(value || "—").replace(/_/g, " ")}
    </span>
  );
}

export function SkeletonRow({ cols = 5 }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3"><div className="glc-skel h-3.5 w-3/4" /></td>
      ))}
    </tr>
  );
}

const GRID_PAGE = 50;

// Plain text of one cell for the CSV: a column can give `csv: (row) => text`; otherwise the raw value (objects are left out).
// A value that starts with = + - @ is prefixed with ' so a spreadsheet does not run it as a formula.
function csvCell(c, r) {
  let v = c.csv ? c.csv(r) : r[c.key];
  if (v === null || v === undefined || typeof v === "object") v = "";
  v = String(v);
  if (/^[=+\-@]/.test(v) && Number.isNaN(Number(v))) v = "'" + v;
  return `"${v.replace(/"/g, '""')}"`;
}

function gridCsv(columns, rows) {
  const cols = columns.filter((c) => c.header && c.csv !== false && (c.csv || rows.some((r) => r[c.key] !== undefined)));
  const lines = [cols.map((c) => `"${String(c.header).replace(/"/g, '""')}"`).join(",")];
  rows.forEach((r) => lines.push(cols.map((c) => csvCell(c, r)).join(",")));
  return "\ufeff" + lines.join("\r\n");        // the marker lets Excel read Hindi correctly
}

function sortValue(c, r) {
  const v = c.sortValue ? c.sortValue(r) : r[c.key];
  if (v === null || v === undefined || typeof v === "object") return null;
  return v;
}

export function DataGrid({ columns, rows, loading, empty, testId = "data-grid", onRowClick, exportName, noExport = false }) {
  const [sort, setSort] = React.useState({ key: null, dir: 1 });
  const [page, setPage] = React.useState(1);
  const list = rows || [];

  const sorted = React.useMemo(() => {
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return list;
    return [...list].sort((a, b) => {
      const x = sortValue(col, a); const y = sortValue(col, b);
      if (x === null && y === null) return 0;
      if (x === null) return 1;                    // empty values always last
      if (y === null) return -1;
      const nx = Number(x); const ny = Number(y);
      const r = (Number.isFinite(nx) && Number.isFinite(ny) && x !== "" && y !== "") ? nx - ny : String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: "base" });
      return r * sort.dir;
    });
  }, [list, columns, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / GRID_PAGE));
  const cur = Math.min(page, pages);
  const shown = sorted.slice((cur - 1) * GRID_PAGE, cur * GRID_PAGE);

  const toggleSort = (c) => {
    if (c.sort === false) return;
    setSort((s) => (s.key === c.key ? { key: c.key, dir: -s.dir } : { key: c.key, dir: 1 }));
    setPage(1);
  };
  const download = () => {
    const blob = new Blob([gridCsv(columns, sorted)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${exportName || testId.replace(/-grid$/, "")}-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  };

  return (
    <div data-testid={testId} className="bg-white rounded-2xl border border-slate-200/70 card-elev overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 sticky top-0 z-[1]">
              {columns.map((c) => (
                <th
                  key={c.key}
                  onClick={() => toggleSort(c)}
                  aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : undefined}
                  className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 text-left select-none ${c.sort === false ? "" : "cursor-pointer hover:text-slate-800"} ${c.align === "right" ? "text-right" : ""}`}
                >
                  {c.header}{sort.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} cols={columns.length} />)}
            {!loading && list.length === 0 && (
              <tr><td colSpan={columns.length} className="px-4 py-12 text-center text-slate-500 text-[13px]">{empty || "No records found."}</td></tr>
            )}
            {!loading && shown.map((r, idx) => (
              <tr
                key={r.id || idx}
                onClick={() => onRowClick && onRowClick(r)}
                className={`border-b border-slate-100 last:border-0 hover:bg-emerald-50/40 transition-colors ${onRowClick ? "cursor-pointer" : ""}`}
              >
                {columns.map((c) => (
                  <td key={c.key} className={`px-4 py-3 text-slate-800 ${c.align === "right" ? "text-right" : ""} ${c.mono ? "font-mono tabular text-[12.5px]" : ""}`}>
                    {c.render ? c.render(r) : r[c.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && list.length > 0 && (!noExport || pages > 1) && (
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-slate-100 text-[12.5px] text-slate-600" data-testid={`${testId}-foot`}>
          <span>{pages > 1 ? `${(cur - 1) * GRID_PAGE + 1}-${Math.min(cur * GRID_PAGE, sorted.length)} of ${sorted.length}` : `${sorted.length} record${sorted.length === 1 ? "" : "s"}`}</span>
          <div className="flex items-center gap-2">
            {pages > 1 && (
              <>
                <button type="button" disabled={cur <= 1} onClick={() => setPage(cur - 1)} className="px-3 h-8 rounded-lg border border-slate-200 bg-white disabled:opacity-40">Previous</button>
                <span>Page {cur} of {pages}</span>
                <button type="button" disabled={cur >= pages} onClick={() => setPage(cur + 1)} className="px-3 h-8 rounded-lg border border-slate-200 bg-white disabled:opacity-40">Next</button>
              </>
            )}
            {!noExport && <button type="button" onClick={download} className="px-3 h-8 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 font-medium" data-testid={`${testId}-csv`}>Download CSV</button>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Pager({ page, total, limit = 50, onPage, testId = "pager" }) {
  const pages = Math.max(1, Math.ceil((total || 0) / limit));
  if ((total || 0) <= limit) return total ? <div data-testid={testId} className="text-[12.5px] text-slate-500">{total} record{total === 1 ? "" : "s"}</div> : null;
  const from = (page - 1) * limit + 1;
  const to = Math.min(page * limit, total);
  return (
    <div data-testid={testId} className="flex items-center justify-between text-[12.5px] text-slate-600">
      <span>{from}-{to} of {total}</span>
      <div className="flex items-center gap-2">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="px-3 h-9 rounded-lg border border-slate-200 bg-white disabled:opacity-40">Previous</button>
        <span>Page {page} of {pages}</span>
        <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="px-3 h-9 rounded-lg border border-slate-200 bg-white disabled:opacity-40">Next</button>
      </div>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  return (
    <div className="bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl p-5 text-[13px] flex items-center justify-between gap-3">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="px-3 h-9 rounded-lg bg-white border border-rose-200 text-[13px] font-medium">Retry</button>}
    </div>
  );
}

