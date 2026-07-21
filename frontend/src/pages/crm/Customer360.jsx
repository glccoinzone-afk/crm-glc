import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Mail, Phone, MapPin, Building2, Receipt, ShoppingCart, LifeBuoy, IndianRupee } from "lucide-react";
import api, { fmtInr, fmtDate } from "@/lib/glc";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader, StatusBadge, StatCard } from "@/components/common/GlcUI";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export default function Customer360() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/customers/${id}`).then((r) => setData(r.data)); }, [id]);
  if (!data) return <div className="glc-skel h-40 w-full" />;
  const c = data.customer;
  const initials = (c.name || "?").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
  const totalSpent = (data.invoices || []).reduce((s, i) => s + (i.total || 0), 0);
  const totalDue = (data.invoices || []).reduce((s, i) => s + (i.dueAmount || 0), 0);

  return (
    <div className="space-y-6">
      <Link to="/crm/customers" className="inline-flex items-center gap-1 text-[13px] text-slate-500 hover:text-slate-800">
        <ArrowLeft size={14} /> Back to customers
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white rounded-2xl border border-slate-200/70 card-elev p-6" data-testid="customer-profile">
          <div className="flex items-start gap-3">
            <Avatar className="w-14 h-14"><AvatarFallback className="bg-[hsl(var(--primary))] text-white text-[16px]">{initials}</AvatarFallback></Avatar>
            <div>
              <div className="text-[17px] font-semibold text-slate-900">{c.name}</div>
              <div className="text-[13px] text-slate-500">{c.company || c.type}</div>
              <div className="mt-1"><StatusBadge value={c.type} /></div>
            </div>
          </div>
          <div className="mt-5 space-y-2.5 text-[13px]">
            {c.email && <div className="flex items-center gap-2 text-slate-700"><Mail size={13} className="text-slate-400" /> {c.email}</div>}
            {c.phone && <div className="flex items-center gap-2 text-slate-700"><Phone size={13} className="text-slate-400" /> {c.phone}</div>}
            {c.state && <div className="flex items-center gap-2 text-slate-700"><MapPin size={13} className="text-slate-400" /> {c.state}</div>}
            {c.gst && <div className="flex items-center gap-2 text-slate-700"><Building2 size={13} className="text-slate-400" /> <span className="font-mono">{c.gst}</span></div>}
          </div>
        </div>
        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Orders" value={(data.orders || []).length} icon={ShoppingCart} tone="primary" />
          <StatCard label="Total Invoiced" value={fmtInr(totalSpent)} icon={Receipt} tone="accent" />
          <StatCard label="Outstanding" value={fmtInr(totalDue)} icon={IndianRupee} tone="danger" />
          <StatCard label="Support Tickets" value={(data.tickets || []).length} icon={LifeBuoy} tone="warn" />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-5">
        <Tabs defaultValue="orders">
          <TabsList className="bg-slate-50">
            <TabsTrigger value="orders">Orders</TabsTrigger>
            <TabsTrigger value="invoices">Invoices</TabsTrigger>
            <TabsTrigger value="payments">Payments</TabsTrigger>
            <TabsTrigger value="tickets">Support</TabsTrigger>
          </TabsList>
          <TabsContent value="orders" className="mt-4">
            <SimpleTable
              cols={[["Order", "orderNo", true], ["Date", "createdAt", false, fmtDate], ["Status", "status", false, (v) => <StatusBadge value={v} />], ["Total", "total", true, fmtInr]]}
              rows={data.orders || []}
            />
          </TabsContent>
          <TabsContent value="invoices" className="mt-4">
            <SimpleTable
              cols={[["Invoice", "invoiceNo", true], ["Date", "invoiceDate", false, fmtDate], ["Due", "dueDate", false, fmtDate], ["Status", "status", false, (v) => <StatusBadge value={v} />], ["Total", "total", true, fmtInr], ["Due Amt", "dueAmount", true, fmtInr]]}
              rows={data.invoices || []}
            />
          </TabsContent>
          <TabsContent value="payments" className="mt-4">
            <SimpleTable cols={[["Date", "date", false, fmtDate], ["Method", "method"], ["Reference", "reference"], ["Amount", "amount", true, fmtInr]]} rows={data.payments || []} />
          </TabsContent>
          <TabsContent value="tickets" className="mt-4">
            <SimpleTable
              cols={[["Ticket", "ticketNo", true], ["Subject", "subject"], ["Priority", "priority", false, (v) => <StatusBadge value={v} />], ["Status", "status", false, (v) => <StatusBadge value={v} />]]}
              rows={data.tickets || []}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function SimpleTable({ cols, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-slate-100">
            {cols.map((c) => (<th key={c[1]} className="text-left px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">{c[0]}</th>))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={cols.length} className="px-3 py-8 text-center text-slate-500 text-[13px]">No records.</td></tr>}
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-slate-50">
              {cols.map(([_, k, mono, fmt]) => (
                <td key={k} className={`px-3 py-2.5 ${mono ? "font-mono tabular text-[12.5px]" : ""} text-slate-800`}>
                  {fmt ? fmt(r[k]) : (r[k] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
