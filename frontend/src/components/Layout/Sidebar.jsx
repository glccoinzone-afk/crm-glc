import React, { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard, Users, UserSquare2, Kanban, FileText, ShoppingCart, Receipt,
  Package, Warehouse, Truck, Building2, ClipboardList, UserRound, CalendarClock,
  Wallet, BarChart3, FolderKanban, LifeBuoy, FileArchive, Settings2, ScrollText,
  Sparkles, BookOpen, Search, ChevronDown, MessageSquare, Megaphone, Bot, Send, CalendarDays, TrendingUp, Store, MessageCircle, Link2
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { canAccess } from "@/lib/rbac";
import { useMobileNav } from "@/context/MobileNavContext";
import { X } from "lucide-react";
import api from "@/lib/glc";

const groups = [
  {
    label: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true, mod: "dashboard" },
    ],
  },
  {
    label: "CRM",
    items: [
      { to: "/crm/leads", label: "Leads", icon: UserSquare2, mod: "crm.leads" },
      { to: "/crm/customers", label: "Customers", icon: Users, mod: "crm.customers" },
      { to: "/crm/pipeline", label: "Sales Pipeline", icon: Kanban, mod: "crm.pipeline" },
      { to: "/crm/quotations", label: "Quotations", icon: FileText, mod: "crm.quotations" },
    ],
  },
  {
    label: "Sales",
    items: [
      { to: "/sales/orders", label: "Orders", icon: ShoppingCart, mod: "sales.orders" },
      { to: "/sales/invoices", label: "Invoices", icon: Receipt, mod: "sales.invoices" },
    ],
  },
  {
    label: "Inventory & Purchase",
    items: [
      { to: "/inventory/products", label: "Products", icon: Package, mod: "inventory.products" },
      { to: "/inventory/stock", label: "Stock", icon: Warehouse, mod: "inventory.stock" },
      { to: "/purchase/suppliers", label: "Suppliers", icon: Building2, mod: "purchase.suppliers" },
      { to: "/purchase/orders", label: "Purchase Orders", icon: ClipboardList, mod: "purchase.orders" },
      { to: "/delivery", label: "Deliveries", icon: Truck, mod: "delivery" },
    ],
  },
  {
    label: "Omnichannel",
    items: [
      { to: "/ocm/whatsapp", label: "WhatsApp", icon: MessageCircle, mod: "ocm.whatsapp" },
      { to: "/ocm/inbox", label: "Inbox", icon: MessageSquare, mod: "ocm.inbox" },
      { to: "/ocm/contacts", label: "Contacts", icon: Users, mod: "ocm.contacts" },
      { to: "/ocm/templates", label: "Templates", icon: FileText, mod: "ocm.templates" },
      { to: "/ocm/campaigns", label: "Campaigns", icon: Megaphone, mod: "ocm.campaigns" },
      { to: "/ocm/broadcasts", label: "Quick Broadcast", icon: Send, mod: "ocm.broadcasts" },
      { to: "/ocm/links", label: "Short Links", icon: Link2, mod: "ocm.links" },
      { to: "/ocm/flows", label: "Chatbot Flows", icon: Bot, mod: "ocm.flows" },
      { to: "/ocm/social", label: "Social Scheduler", icon: Send, mod: "ocm.social" },
      { to: "/ocm/calendar", label: "Content Calendar", icon: CalendarDays, mod: "ocm.calendar" },
      { to: "/sellers", label: "Seller Management", icon: Store, mod: "*" },
    ],
  },
  {
    label: "HR",
    items: [
      { to: "/hr/employees", label: "Employees", icon: UserRound, mod: "hr.employees" },
      { to: "/hr/attendance", label: "Attendance", icon: CalendarClock, mod: "hr.attendance" },
      { to: "/hr/leaves", label: "Leaves", icon: CalendarClock, mod: "hr.leaves" },
      { to: "/hr/payroll", label: "Payroll", icon: Wallet, mod: "hr.payroll" },
    ],
  },
  {
    label: "Finance",
    items: [
      { to: "/finance/accounts", label: "Chart of Accounts", icon: BarChart3, mod: "finance.accounts" },
      { to: "/finance/journal", label: "Journal", icon: ScrollText, mod: "finance.journal" },
      { to: "/finance/gst", label: "GST Reports", icon: FileText, mod: "finance.gst" },
      { to: "/finance/gst-returns", label: "GSTR-1 / 3B", icon: FileText, mod: "finance.gst" },
      { to: "/finance/trial-balance", label: "Trial Balance", icon: BarChart3, mod: "finance.trial" },
      { to: "/finance/ageing", label: "Receivables Ageing", icon: CalendarClock, mod: "finance.ageing" },
      { to: "/sales/credit-notes", label: "Credit Notes", icon: ScrollText, mod: "sales.invoices" },
      { to: "/finance/pl", label: "Profit & Loss", icon: TrendingUp, mod: "finance.pl" },
      { to: "/finance/expenses", label: "Expenses", icon: Wallet, mod: "finance.expenses" },
    ],
  },
  {
    label: "Work",
    items: [
      { to: "/projects", label: "Projects", icon: FolderKanban, mod: "projects" },
      { to: "/tasks", label: "Tasks", icon: Kanban, mod: "tasks" },
      { to: "/tickets", label: "Support Tickets", icon: LifeBuoy, mod: "tickets" },
      { to: "/documents", label: "Documents", icon: FileArchive, mod: "documents" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/guide", label: "How it works", icon: BookOpen, mod: "dashboard" },
      { to: "/audit", label: "Audit Log", icon: ScrollText, mod: "audit" },
      { to: "/settings", label: "Settings", icon: Settings2, mod: "settings" },
    ],
  },
];

const OPEN_KEY = "glc_sidebar_open";
const readOpen = () => { try { return JSON.parse(localStorage.getItem(OPEN_KEY) || "{}"); } catch { return {}; } };

export default function Sidebar() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { mobileOpen, closeMobile } = useMobileNav();
  const role = user?.role || "Admin";
  const [q, setQ] = useState("");
  const [closed, setClosed] = useState(readOpen);
  const [unread, setUnread] = useState(0);

  const visible = useMemo(() => groups.map((g) => ({
    ...g,
    items: g.items.filter((it) => canAccess(role, it.mod, user?.modules)),
  })).filter((g) => g.items.length > 0), [role, user]);

  const canInbox = canAccess(role, "ocm.inbox", user?.modules);
  useEffect(() => {
    if (!canInbox) return undefined;
    const load = () => api.get("/ocm/conversations").then((r) => setUnread((r.data.items || []).reduce((a, c) => a + (c.unread || 0), 0))).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [canInbox]);

  const toggle = (label) => setClosed((c) => {
    const n = { ...c, [label]: !c[label] };
    try { localStorage.setItem(OPEN_KEY, JSON.stringify(n)); } catch { /* storage unavailable */ }
    return n;
  });

  const term = q.trim().toLowerCase();
  const shown = visible
    .map((g) => ({ ...g, items: term ? g.items.filter((it) => it.label.toLowerCase().includes(term)) : g.items }))
    .filter((g) => g.items.length > 0);
  const initials = (user?.name || "GZ").split(" ").map((x) => x[0]).join("").slice(0, 2).toUpperCase();

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={closeMobile} data-testid="sidebar-backdrop" />}
      <aside
        data-testid="app-sidebar"
        className={"glc-side flex flex-col fixed top-0 bottom-0 left-0 w-[264px] z-50 transition-transform duration-200 " + (mobileOpen ? "translate-x-0" : "-translate-x-full") + " lg:translate-x-0"}
      >
        <div className="px-5 pt-5 pb-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white grid place-items-center shadow-lg shadow-emerald-900/30">
            <Sparkles size={18} strokeWidth={2} />
          </div>
          <div className="flex-1">
            <div className="text-[15px] font-semibold tracking-tight text-white leading-4">GLC Zone</div>
            <div className="text-[11px] text-emerald-200/60 mt-0.5">CRM + ERP</div>
          </div>
          <button onClick={closeMobile} className="lg:hidden p-1.5 rounded-lg hover:bg-white/10" data-testid="sidebar-close"><X size={18} className="text-white/70" /></button>
        </div>

        <div className="px-4 pb-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a page" className="w-full h-9 pl-9 pr-3 rounded-lg bg-white/[0.07] text-[13px] text-white placeholder:text-white/35 outline-none focus:bg-white/[0.11]" />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4 glc-side-scroll">
          {shown.map((g) => {
            const isClosed = !term && closed[g.label];
            return (
              <div key={g.label} className="mb-1">
                <button onClick={() => toggle(g.label)} className="w-full flex items-center justify-between px-3 py-2 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-white/40 hover:text-white/70">
                  {g.label}
                  <ChevronDown size={13} className={`transition-transform ${isClosed ? "-rotate-90" : ""}`} />
                </button>
                {!isClosed && (
                  <ul className="space-y-0.5 mb-2">
                    {g.items.map((it) => {
                      const Icon = it.icon;
                      const active = it.exact ? pathname === it.to : pathname.startsWith(it.to);
                      return (
                        <li key={it.to}>
                          <NavLink
                            to={it.to}
                            onClick={closeMobile}
                            data-testid={`nav-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
                            data-active={active}
                            className="glc-side-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13.5px]"
                          >
                            <Icon size={16} strokeWidth={1.75} />
                            <span>{it.label}</span>
                            {it.to === "/ocm/inbox" && unread > 0 && <span className="ml-auto min-w-[20px] h-5 px-1.5 rounded-full bg-[#25D366] text-white text-[11px] font-semibold grid place-items-center">{unread}</span>}
                          </NavLink>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })}
          {shown.length === 0 && <div className="px-3 py-6 text-[13px] text-white/40">No page matches "{q}"</div>}
        </nav>

        <div className="px-4 py-3 border-t border-white/10 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-200 grid place-items-center text-[12px] font-semibold">{initials}</div>
          <div className="min-w-0">
            <div className="text-[12.5px] font-medium text-white truncate">{user?.name}</div>
            <div className="text-[11px] text-white/45 truncate">{user?.role}</div>
          </div>
        </div>
      </aside>
    </>
  );
}
