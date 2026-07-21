import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard, Users, UserSquare2, Kanban, FileText, ShoppingCart, Receipt,
  Package, Warehouse, Truck, Building2, ClipboardList, UserRound, CalendarClock,
  Wallet, BarChart3, FolderKanban, LifeBuoy, FileArchive, Settings2, ScrollText,
  Sparkles
} from "lucide-react";

const groups = [
  {
    label: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
    ],
  },
  {
    label: "CRM",
    items: [
      { to: "/crm/leads", label: "Leads", icon: UserSquare2 },
      { to: "/crm/customers", label: "Customers", icon: Users },
      { to: "/crm/pipeline", label: "Sales Pipeline", icon: Kanban },
      { to: "/crm/quotations", label: "Quotations", icon: FileText },
    ],
  },
  {
    label: "Sales",
    items: [
      { to: "/sales/orders", label: "Orders", icon: ShoppingCart },
      { to: "/sales/invoices", label: "Invoices", icon: Receipt },
    ],
  },
  {
    label: "Inventory & Purchase",
    items: [
      { to: "/inventory/products", label: "Products", icon: Package },
      { to: "/inventory/stock", label: "Stock", icon: Warehouse },
      { to: "/purchase/suppliers", label: "Suppliers", icon: Building2 },
      { to: "/purchase/orders", label: "Purchase Orders", icon: ClipboardList },
      { to: "/delivery", label: "Deliveries", icon: Truck },
    ],
  },
  {
    label: "HR",
    items: [
      { to: "/hr/employees", label: "Employees", icon: UserRound },
      { to: "/hr/attendance", label: "Attendance", icon: CalendarClock },
      { to: "/hr/leaves", label: "Leaves", icon: CalendarClock },
      { to: "/hr/payroll", label: "Payroll", icon: Wallet },
    ],
  },
  {
    label: "Finance",
    items: [
      { to: "/finance/accounts", label: "Chart of Accounts", icon: BarChart3 },
      { to: "/finance/journal", label: "Journal", icon: ScrollText },
      { to: "/finance/gst", label: "GST Reports", icon: FileText },
      { to: "/finance/expenses", label: "Expenses", icon: Wallet },
    ],
  },
  {
    label: "Work",
    items: [
      { to: "/projects", label: "Projects", icon: FolderKanban },
      { to: "/tasks", label: "Tasks", icon: Kanban },
      { to: "/tickets", label: "Support Tickets", icon: LifeBuoy },
      { to: "/documents", label: "Documents", icon: FileArchive },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/audit", label: "Audit Log", icon: ScrollText },
      { to: "/settings", label: "Settings", icon: Settings2 },
    ],
  },
];

export default function Sidebar() {
  const { pathname } = useLocation();
  return (
    <aside
      data-testid="app-sidebar"
      className="hidden lg:flex flex-col fixed left-4 top-4 bottom-4 w-[260px] bg-white rounded-2xl card-elev overflow-hidden z-30"
    >
      <div className="px-5 pt-5 pb-4 flex items-center gap-2">
        <div className="w-9 h-9 rounded-xl bg-[hsl(var(--primary))] text-white grid place-items-center">
          <Sparkles size={18} strokeWidth={2} />
        </div>
        <div>
          <div className="text-[15px] font-semibold tracking-tight text-slate-900 leading-4">GLC Zone</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Enterprise CRM + ERP</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {groups.map((g) => (
          <div key={g.label} className="mb-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400 px-3 mb-1.5">
              {g.label}
            </div>
            <ul className="space-y-0.5">
              {g.items.map((it) => {
                const Icon = it.icon;
                const active = it.exact ? pathname === it.to : pathname.startsWith(it.to);
                return (
                  <li key={it.to}>
                    <NavLink
                      to={it.to}
                      data-testid={`nav-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
                      data-active={active}
                      className="side-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13.5px] text-slate-700 hover:bg-slate-50"
                    >
                      <Icon size={16} strokeWidth={1.75} className={active ? "text-[hsl(var(--primary))]" : "text-slate-500"} />
                      <span className={active ? "font-medium text-slate-900" : ""}>{it.label}</span>
                      {active && (
                        <motion.span layoutId="side-dot" className="ml-auto w-1.5 h-1.5 rounded-full bg-[hsl(var(--primary))]" />
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-slate-100 text-[11px] text-slate-400">
        v1.0.0 · India-first ERP
      </div>
    </aside>
  );
}
