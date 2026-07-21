import React from "react";
import { motion } from "framer-motion";

export function PageHeader({ title, subtitle, actions, testId = "page-header" }) {
  return (
    <div data-testid={testId} className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
      <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl md:text-[28px] font-semibold tracking-tight text-slate-900">{title}</h1>
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
      className="bg-white rounded-2xl border border-slate-200/70 p-5 card-elev"
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

export function DataGrid({ columns, rows, loading, empty, testId = "data-grid", onRowClick }) {
  return (
    <div data-testid={testId} className="bg-white rounded-2xl border border-slate-200/70 card-elev overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-slate-50/80 backdrop-blur-sm border-b border-slate-200">
              {columns.map((c) => (
                <th key={c.key} className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 text-left ${c.align === "right" ? "text-right" : ""}`}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} cols={columns.length} />)}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={columns.length} className="px-4 py-12 text-center text-slate-500 text-[13px]">{empty || "No records found."}</td></tr>
            )}
            {!loading && rows.map((r, idx) => (
              <tr
                key={r.id || idx}
                onClick={() => onRowClick && onRowClick(r)}
                className={`border-b border-slate-100 hover:bg-slate-50/70 ${onRowClick ? "cursor-pointer" : ""}`}
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
    </div>
  );
}
