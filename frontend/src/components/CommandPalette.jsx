import React, { useEffect, useMemo, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import api from "@/lib/glc";
import {
  LayoutDashboard, UserSquare2, Users, Kanban, FileText, ShoppingCart, Receipt,
  Package, Warehouse, Building2, ClipboardList, Truck, UserRound, CalendarClock,
  Wallet, BarChart3, FolderKanban, LifeBuoy, FileArchive, Settings2, ScrollText,
  MessageSquare, Send, Megaphone, Bot, CalendarDays, Search
} from "lucide-react";

const NAV = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard },
  { label: "Leads", to: "/crm/leads", icon: UserSquare2 },
  { label: "Customers", to: "/crm/customers", icon: Users },
  { label: "Sales Pipeline", to: "/crm/pipeline", icon: Kanban },
  { label: "Quotations", to: "/crm/quotations", icon: FileText },
  { label: "Orders", to: "/sales/orders", icon: ShoppingCart },
  { label: "Invoices", to: "/sales/invoices", icon: Receipt },
  { label: "Products", to: "/inventory/products", icon: Package },
  { label: "Stock", to: "/inventory/stock", icon: Warehouse },
  { label: "Suppliers", to: "/purchase/suppliers", icon: Building2 },
  { label: "Purchase Orders", to: "/purchase/orders", icon: ClipboardList },
  { label: "Deliveries", to: "/delivery", icon: Truck },
  { label: "Employees", to: "/hr/employees", icon: UserRound },
  { label: "Attendance", to: "/hr/attendance", icon: CalendarClock },
  { label: "Leaves", to: "/hr/leaves", icon: CalendarClock },
  { label: "Payroll", to: "/hr/payroll", icon: Wallet },
  { label: "Chart of Accounts", to: "/finance/accounts", icon: BarChart3 },
  { label: "Journal", to: "/finance/journal", icon: ScrollText },
  { label: "GST Reports", to: "/finance/gst", icon: FileText },
  { label: "Expenses", to: "/finance/expenses", icon: Wallet },
  { label: "Projects", to: "/projects", icon: FolderKanban },
  { label: "Tasks", to: "/tasks", icon: Kanban },
  { label: "Support Tickets", to: "/tickets", icon: LifeBuoy },
  { label: "Documents", to: "/documents", icon: FileArchive },
  { label: "Omnichannel Inbox", to: "/ocm/inbox", icon: MessageSquare },
  { label: "Contacts", to: "/ocm/contacts", icon: Users },
  { label: "Broadcasts", to: "/ocm/broadcasts", icon: Megaphone },
  { label: "Chatbot Flows", to: "/ocm/flows", icon: Bot },
  { label: "Social Scheduler", to: "/ocm/social", icon: Send },
  { label: "Content Calendar", to: "/ocm/calendar", icon: CalendarDays },
  { label: "Audit Log", to: "/audit", icon: ScrollText },
  { label: "Settings", to: "/settings", icon: Settings2 },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [dynamic, setDynamic] = useState({ leads: [], customers: [], products: [], invoices: [] });
  const nav = useNavigate();

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    if (value.length < 2) return;
    let cancel = false;
    const q = value;
    Promise.all([
      api.get("/leads", { params: { q, limit: 5 } }).catch(() => ({ data: { items: [] } })),
      api.get("/customers", { params: { q, limit: 5 } }).catch(() => ({ data: { items: [] } })),
      api.get("/products", { params: { q, limit: 5 } }).catch(() => ({ data: { items: [] } })),
      api.get("/invoices", { params: { q, limit: 5 } }).catch(() => ({ data: { items: [] } })),
    ]).then(([a, b, c, d]) => {
      if (cancel) return;
      setDynamic({ leads: a.data.items || [], customers: b.data.items || [], products: c.data.items || [], invoices: d.data.items || [] });
    });
    return () => { cancel = true; };
  }, [value, open]);

  const go = (to) => { setOpen(false); setValue(""); nav(to); };

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-[70] bg-slate-900/40 backdrop-blur-sm grid place-items-start pt-24" onClick={() => setOpen(false)} data-testid="command-palette">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden">
            <Command shouldFilter={true} className="w-full">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
                <Search size={16} className="text-slate-400" />
                <Command.Input
                  autoFocus
                  value={value}
                  onValueChange={setValue}
                  placeholder="Search modules, leads, customers, products, invoices…"
                  className="flex-1 outline-none text-[14px] placeholder:text-slate-400"
                  data-testid="command-input"
                />
                <kbd className="text-[10px] font-mono text-slate-400 border border-slate-200 rounded px-1.5 py-0.5">ESC</kbd>
              </div>
              <Command.List className="max-h-[420px] overflow-y-auto p-2">
                <Command.Empty className="py-8 text-center text-[13px] text-slate-500">No results found.</Command.Empty>

                <Command.Group heading="Navigate" className="text-[10.5px] uppercase tracking-wide text-slate-400 font-semibold px-2 py-1">
                  {NAV.map((n) => {
                    const Icon = n.icon;
                    return (
                      <Command.Item key={n.to} value={`nav ${n.label}`} onSelect={() => go(n.to)} className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] text-slate-700 cursor-pointer aria-selected:bg-slate-100">
                        <Icon size={14} className="text-slate-500" /> {n.label}
                      </Command.Item>
                    );
                  })}
                </Command.Group>

                {dynamic.leads.length > 0 && (
                  <Command.Group heading="Leads" className="text-[10.5px] uppercase tracking-wide text-slate-400 font-semibold px-2 py-1 mt-2">
                    {dynamic.leads.map((l) => (
                      <Command.Item key={l.id} value={`lead ${l.name} ${l.email || ""}`} onSelect={() => go(`/crm/leads`)} className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] cursor-pointer aria-selected:bg-slate-100">
                        <UserSquare2 size={14} className="text-slate-500" />
                        <span className="text-slate-800">{l.name}</span><span className="text-slate-400 text-[11px]">{l.company || l.email}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
                {dynamic.customers.length > 0 && (
                  <Command.Group heading="Customers" className="text-[10.5px] uppercase tracking-wide text-slate-400 font-semibold px-2 py-1 mt-2">
                    {dynamic.customers.map((c) => (
                      <Command.Item key={c.id} value={`cust ${c.name} ${c.email || ""}`} onSelect={() => go(`/crm/customers/${c.id}`)} className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] cursor-pointer aria-selected:bg-slate-100">
                        <Users size={14} className="text-slate-500" />
                        <span className="text-slate-800">{c.name}</span><span className="text-slate-400 text-[11px]">{c.company || c.gst}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
                {dynamic.products.length > 0 && (
                  <Command.Group heading="Products" className="text-[10.5px] uppercase tracking-wide text-slate-400 font-semibold px-2 py-1 mt-2">
                    {dynamic.products.map((p) => (
                      <Command.Item key={p.id} value={`prod ${p.name} ${p.sku}`} onSelect={() => go(`/inventory/products`)} className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] cursor-pointer aria-selected:bg-slate-100">
                        <Package size={14} className="text-slate-500" />
                        <span className="text-slate-800">{p.name}</span><span className="text-slate-400 text-[11px] font-mono">{p.sku}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
                {dynamic.invoices.length > 0 && (
                  <Command.Group heading="Invoices" className="text-[10.5px] uppercase tracking-wide text-slate-400 font-semibold px-2 py-1 mt-2">
                    {dynamic.invoices.map((i) => (
                      <Command.Item key={i.id} value={`inv ${i.invoiceNo} ${i.customerName || ""}`} onSelect={() => go(`/sales/invoices`)} className="flex items-center gap-2 px-2 py-2 rounded-lg text-[13px] cursor-pointer aria-selected:bg-slate-100">
                        <Receipt size={14} className="text-slate-500" />
                        <span className="text-slate-800 font-mono">{i.invoiceNo}</span><span className="text-slate-400 text-[11px]">{i.customerName}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>
              <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <div>Cmd/Ctrl + K to toggle</div>
                <div>↵ to open · ↑↓ to navigate</div>
              </div>
            </Command>
          </div>
        </div>
      )}
    </>
  );
}
