import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from "recharts";
import { ShoppingCart, IndianRupee, Users, Package, Receipt, LifeBuoy, UserSquare2, Truck, UserRound, CalendarCheck2, ArrowUpRight, Sparkles, TriangleAlert, BadgeIndianRupee } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { useVertical, useAuth } from "@/context/AuthContext";
import { canAccess } from "@/lib/rbac";
import { PageHeader, StatCard, StatusBadge } from "@/components/common/GlcUI";
import { Link } from "react-router-dom";

const CHART = ["#064E3B", "#10B981", "#F59E0B", "#EA580C", "#6366F1", "#0EA5E9", "#EC4899", "#14B8A6"];

function ChartCard({ title, subtitle, children, action, testId }) {
  return (
    <div data-testid={testId} className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-[14.5px] font-semibold text-slate-900">{title}</div>
          {subtitle && <div className="text-[12px] text-slate-500 mt-0.5">{subtitle}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const { vertical } = useVertical();
  const { user } = useAuth();
  const role = user?.role || "Admin";
  const mods = user?.modules;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = vertical !== "ALL" ? { vertical } : {};
    api.get("/dashboard", { params }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [vertical]);

  const k = data?.kpi || {};

  const allKpiCards = [
    { label: "Today's Revenue", value: fmtInr(k.todayRevenue), icon: IndianRupee, tone: "primary", testId: "kpi-revenue", mod: "sales.orders" },
    { label: "Today's Orders", value: k.todayOrders ?? 0, icon: ShoppingCart, tone: "accent", testId: "kpi-orders", mod: "sales.orders" },
    { label: "New Customers", value: k.newCustomers ?? 0, icon: Users, tone: "success", testId: "kpi-customers", mod: "crm.customers" },
    { label: "Pending Orders", value: k.pendingOrders ?? 0, icon: Package, tone: "warn", testId: "kpi-pending-orders", mod: "sales.orders" },
    { label: "Unpaid Invoices", value: fmtInr(k.unpaidAmount), icon: Receipt, tone: "danger", testId: "kpi-unpaid", mod: "sales.invoices" },
    { label: "Open Tickets", value: k.openTickets ?? 0, icon: LifeBuoy, tone: "slate", testId: "kpi-tickets", mod: "tickets" },
    { label: "Total Leads", value: k.totalLeads ?? 0, icon: UserSquare2, tone: "primary", testId: "kpi-leads", mod: "crm.leads" },
    { label: "Pending Deliveries", value: k.pendingDeliveries ?? 0, icon: Truck, tone: "accent", testId: "kpi-deliveries", mod: "delivery" },
    { label: "Employees", value: k.employeeCount ?? 0, icon: UserRound, tone: "slate", testId: "kpi-employees", mod: "hr.employees" },
    { label: "Today's Attendance", value: k.todayAttendance ?? 0, icon: CalendarCheck2, tone: "success", testId: "kpi-attendance", mod: "hr.attendance" },
  ];

  const kpiCards = allKpiCards.filter((c) => canAccess(role, c.mod, mods));

  return (
    <div className="space-y-6">
      <PageHeader
        testId="dashboard-header"
        title="Executive Dashboard"
        subtitle={`${vertical === "ALL" ? "All verticals" : vertical} · Real-time performance across the business`}
        actions={
          <Link to="/crm/leads" className="hidden md:inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
            <Sparkles size={14} /> New Lead
          </Link>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4" data-testid="kpi-grid">
        {(loading ? Array.from({ length: 10 }) : kpiCards).map((c, i) => loading ? (
          <div key={i} className="bg-white rounded-2xl border border-slate-200/70 p-5 card-elev">
            <div className="glc-skel h-3 w-24 mb-3" />
            <div className="glc-skel h-6 w-32" />
          </div>
        ) : (
          <StatCard key={c.label} {...c} />
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {canAccess(role, "sales.orders", mods) && (
        <ChartCard testId="chart-revenue" title="Revenue Trend" subtitle="Last 6 months revenue across the business">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data?.charts?.revenueSeries || []}>
              <defs>
                <linearGradient id="revG" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#064E3B" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#064E3B" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 6" stroke="#E5E7EB" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} width={50} tickFormatter={(v) => `₹${(v/1000).toFixed(0)}K`} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E7EB", fontSize: 12 }} formatter={(v) => fmtInr(v)} />
              <Area type="monotone" dataKey="revenue" stroke="#064E3B" strokeWidth={2.2} fill="url(#revG)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        )}

        {canAccess(role, "sales.orders", mods) && (
        <ChartCard testId="chart-sales-vertical" title="Sales by Vertical" subtitle="Order value split across GLC verticals">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={data?.charts?.salesByVertical || []} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                {(data?.charts?.salesByVertical || []).map((_, i) => <Cell key={i} fill={CHART[i % CHART.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E7EB", fontSize: 12 }} formatter={(v) => fmtInr(v)} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            {(data?.charts?.salesByVertical || []).slice(0, 6).map((s, i) => (
              <div key={s.name} className="flex items-center gap-2 text-[11.5px]">
                <span className="w-2 h-2 rounded-full" style={{ background: CHART[i % CHART.length] }} />
                <span className="text-slate-600 truncate">{s.name}</span>
              </div>
            ))}
          </div>
        </ChartCard>
        )}

        {canAccess(role, "crm.leads", mods) && (
        <ChartCard testId="chart-funnel" title="Lead Conversion Funnel" subtitle="Leads by pipeline stage">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data?.charts?.leadFunnel || []} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 6" stroke="#E5E7EB" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="stage" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} width={90} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E7EB", fontSize: 12 }} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {(data?.charts?.leadFunnel || []).map((_, i) => <Cell key={i} fill={CHART[i % CHART.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        )}
      </div>

      {/* Bottom row: recent + lowstock + attendance */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {canAccess(role, "sales.orders", mods) && (
        <div className="xl:col-span-2 bg-white rounded-2xl border border-slate-200/70 card-elev">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="text-[14.5px] font-semibold text-slate-900">Recent Orders</div>
              <div className="text-[12px] text-slate-500 mt-0.5">Latest 5 sales orders</div>
            </div>
            <Link to="/sales/orders" className="text-[12px] text-[hsl(var(--primary))] font-medium inline-flex items-center gap-1 hover:underline">View all <ArrowUpRight size={13} /></Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]" data-testid="recent-orders">
              <thead>
                <tr className="bg-slate-50/60 border-b border-slate-100">
                  <th className="px-5 py-2.5 text-left text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Order</th>
                  <th className="px-5 py-2.5 text-left text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Customer</th>
                  <th className="px-5 py-2.5 text-left text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Vertical</th>
                  <th className="px-5 py-2.5 text-left text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Status</th>
                  <th className="px-5 py-2.5 text-right text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold">Amount</th>
                </tr>
              </thead>
              <tbody>
                {(data?.recent?.orders || []).map((o) => (
                  <tr key={o.id} className="border-b border-slate-100">
                    <td className="px-5 py-3 font-mono text-[12px] text-slate-800">{o.orderNo}</td>
                    <td className="px-5 py-3 text-slate-800">{o.customerName}</td>
                    <td className="px-5 py-3 text-slate-500">{o.vertical || "—"}</td>
                    <td className="px-5 py-3"><StatusBadge value={o.status} /></td>
                    <td className="px-5 py-3 text-right font-mono tabular text-slate-900">{fmtInr(o.total)}</td>
                  </tr>
                ))}
                {(!data?.recent?.orders || data.recent.orders.length === 0) && (
                  <tr><td colSpan={5} className="px-5 py-8 text-center text-slate-500 text-[13px]">No orders yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        )}

        <div className="space-y-4">
          {canAccess(role, "inventory.stock", mods) && (
          <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5" data-testid="low-stock">
            <div className="flex items-center gap-2 mb-3">
              <TriangleAlert size={16} className="text-amber-500" />
              <div className="text-[14px] font-semibold text-slate-900">Low Stock Alerts</div>
            </div>
            <ul className="space-y-2.5">
              {(data?.recent?.lowStock || []).map((p) => (
                <li key={p.sku} className="flex items-center justify-between text-[12.5px]">
                  <div>
                    <div className="text-slate-800 font-medium">{p.name}</div>
                    <div className="text-slate-500 text-[11px] font-mono">{p.sku}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono tabular text-rose-600 font-medium">{p.current}</div>
                    <div className="text-[10px] text-slate-400">min {p.min}</div>
                  </div>
                </li>
              ))}
              {(!data?.recent?.lowStock || data.recent.lowStock.length === 0) && (
                <li className="text-[12.5px] text-slate-500">All stock levels are healthy.</li>
              )}
            </ul>
          </div>
          )}

          <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5" data-testid="approvals">
            <div className="flex items-center gap-2 mb-3">
              <BadgeIndianRupee size={16} className="text-[hsl(var(--primary))]" />
              <div className="text-[14px] font-semibold text-slate-900">Pending Approvals</div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "Leaves", val: data?.pending?.leaves, to: "/hr/leaves", mod: "hr.leaves" },
                { label: "Expenses", val: data?.pending?.expenses, to: "/finance/expenses", mod: "finance.expenses" },
                { label: "POs", val: data?.pending?.purchaseOrders, to: "/purchase/orders", mod: "purchase.orders" },
              ].filter((x) => canAccess(role, x.mod, mods)).map((x) => (
                <Link key={x.label} to={x.to} className="rounded-xl border border-slate-100 bg-slate-50 hover:bg-slate-100/70 p-3 text-center">
                  <div className="text-[22px] font-semibold tabular text-slate-900">{x.val ?? 0}</div>
                  <div className="text-[11px] text-slate-500">{x.label}</div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
