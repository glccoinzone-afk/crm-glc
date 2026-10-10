import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Search, ArrowUpRight } from "lucide-react";
import { PageHeader } from "@/components/common/GlcUI";

// What every sidebar page is for and how to use it. Keep this in step with the sidebar.
const GUIDE = [
  {
    group: "Overview",
    items: [
      { to: "/", name: "Dashboard", what: "One-screen health check of the business: revenue, open leads, stock value and the lead funnel.", how: "Switch the business vertical in the top bar to see one store at a time. Numbers refresh whenever you open the page." },
    ],
  },
  {
    group: "CRM",
    items: [
      { to: "/crm/leads", name: "Leads", what: "People who might buy. Each lead has a stage (New, Contacted, Qualified, Proposal, Negotiation, Won, Lost), a score and a follow-up date.", how: "Add a lead, assign it to a teammate, update the stage after each call. Use the follow-up date so nothing is forgotten." },
      { to: "/crm/customers", name: "Customers", what: "People and businesses who have bought. Open one to see the full history: orders, invoices, tickets.", how: "Search by name or phone. A converted lead becomes a customer." },
      { to: "/crm/pipeline", name: "Sales Pipeline", what: "Kanban board of deals by stage.", how: "Drag a deal to the next column as it moves forward. The value of each column adds up at the top." },
      { to: "/crm/quotations", name: "Quotations", what: "Price offers you send before an order.", how: "Create a quotation with products and quantities, share it, and convert it to an order when the customer accepts." },
    ],
  },
  {
    group: "Sales",
    items: [
      { to: "/sales/orders", name: "Orders", what: "Orders from the website and your own CRM orders in one list. Website orders arrive automatically as they are placed.", how: "Open an order to see items, payment and delivery. Use the status to move it forward." },
      { to: "/sales/invoices", name: "Invoices", what: "GST invoices with state-aware CGST/SGST/IGST and a financial-year invoice number. Posting an invoice also writes the accounting entries.", how: "Create from an order, print or email it, record payments against it. Find a website order by its GLZ-number." },
    ],
  },
  {
    group: "Inventory & Purchase",
    items: [
      { to: "/inventory/products", name: "Products", what: "Your catalogue with selling and buying price, GST rate and category.", how: "Add or edit products here; stock is tracked separately per warehouse." },
      { to: "/inventory/stock", name: "Stock", what: "How many units of each product sit in each warehouse.", how: "Adjust stock after counts. Receiving a purchase order adds stock automatically." },
      { to: "/purchase/suppliers", name: "Suppliers", what: "The people you buy from, with contact and GST details.", how: "Add a supplier before raising a purchase order." },
      { to: "/purchase/orders", name: "Purchase Orders", what: "Orders you place with suppliers.", how: "Create, then mark Received when goods arrive. Receiving updates stock and the books." },
      { to: "/delivery", name: "Deliveries", what: "Parcels going out and the riders carrying them. Statuses sync with the website.", how: "Assign a rider, watch the status move from assigned to delivered." },
    ],
  },
  {
    group: "Omnichannel (WhatsApp and more)",
    items: [
      { to: "/ocm/whatsapp", name: "WhatsApp", what: "Overview of your WhatsApp setup and results: reachable contacts, delivered and read rates, and a connection checklist.", how: "Start here. If a checklist step is amber, fix it first. Enter your WhatsApp Business Account ID here." },
      { to: "/ocm/inbox", name: "Inbox", what: "Every customer conversation (WhatsApp, Telegram, website chat) in one place, with unread counts.", how: "Filter Mine / Open / Unread. Assign a chat, add private notes, reply, and type / to use saved replies. WhatsApp only delivers free text within 24 hours of the customer's last message." },
      { to: "/ocm/contacts", name: "Contacts", what: "Your audience list with tags, opt-in status and saved segments.", how: "Import a CSV (name, phone, email, tags), tag people, then save a filter as a segment to reuse in campaigns. Customers who reply STOP are opted out automatically." },
      { to: "/ocm/templates", name: "Templates", what: "Pre-approved WhatsApp messages. WhatsApp requires a template to start a conversation or message people outside the 24-hour window.", how: "Write the text with {{1}} variables, add sample values, submit. Meta reviews it (minutes to hours). Only Approved templates can be used in campaigns." },
      { to: "/ocm/campaigns", name: "Campaigns", what: "Send an approved template to a segment, now or at a scheduled time, and see sent / delivered / read / failed.", how: "New campaign: choose the template, fill the variables, choose the audience (live count shown), send or schedule. Open a campaign to see each number's result and failure reasons." },
      { to: "/ocm/broadcasts", name: "Quick Broadcast", what: "The older simple broadcast: a plain text message to many contacts across channels.", how: "Works only inside the 24-hour window on WhatsApp. For marketing use Campaigns instead." },
      { to: "/ocm/flows", name: "Chatbot Flows", what: "Automatic replies. A keyword (or a first message) triggers a set of messages.", how: "Create a flow, set the keyword, write the messages in order, activate it. If no flow matches, the AI assistant answers." },
      { to: "/ocm/links", name: "Short Links", what: "Short tracked links you can put in messages.", how: "Paste a long URL, copy the short one, and watch the click count." },
      { to: "/ocm/social", name: "Social Scheduler", what: "Plan and publish posts to your social pages.", how: "Write a post, pick channels and a time, then publish or let it go out on schedule." },
      { to: "/ocm/calendar", name: "Content Calendar", what: "Calendar view of everything scheduled.", how: "Use it to spot gaps and clashes in your posting plan." },
      { to: "/sellers", name: "Seller Management", what: "Marketplace sellers connected from the website.", how: "Review sellers, sync them from the store and check their status." },
    ],
  },
  {
    group: "HR",
    items: [
      { to: "/hr/employees", name: "Employees", what: "Staff records and roles.", how: "Add an employee and give them a role; the role decides which pages they can open." },
      { to: "/hr/attendance", name: "Attendance", what: "Daily present, absent, half-day and late marks.", how: "Mark attendance each day; payroll reads from it." },
      { to: "/hr/leaves", name: "Leaves", what: "Leave requests and approvals.", how: "Staff apply, a manager approves or rejects." },
      { to: "/hr/payroll", name: "Payroll", what: "Monthly salary calculation from attendance and leaves.", how: "Run a month, review, and mark paid." },
    ],
  },
  {
    group: "Finance",
    items: [
      { to: "/finance/accounts", name: "Chart of Accounts", what: "The list of accounts the books use (cash, sales, GST payable and so on).", how: "Usually left as is; add an account only when your accountant asks." },
      { to: "/finance/journal", name: "Journal", what: "Every accounting entry. Invoices, payments, purchases and credit notes post here automatically.", how: "Read-only for most people; use it to trace where a number came from." },
      { to: "/finance/gst", name: "GST Reports", what: "Sales and tax summaries by period and rate.", how: "Pick a month and download for your accountant." },
      { to: "/finance/gst-returns", name: "GSTR-1 / 3B", what: "Return-ready figures for GSTR-1 and GSTR-3B.", how: "Pick the month; have your CA review before filing." },
      { to: "/finance/trial-balance", name: "Trial Balance", what: "Debit and credit totals per account, with a ledger drill-down.", how: "Debits and credits should match; click an account to see its entries." },
      { to: "/finance/ageing", name: "Receivables Ageing", what: "Who owes you money and for how long.", how: "Follow up on the oldest buckets first." },
      { to: "/sales/credit-notes", name: "Credit Notes", what: "Reductions against an invoice (returns, corrections).", how: "Create from an invoice; the books and GST adjust automatically." },
      { to: "/finance/pl", name: "Profit & Loss", what: "Income minus expenses for a period.", how: "Pick the dates; expenses come from the Expenses page and purchases." },
      { to: "/finance/expenses", name: "Expenses", what: "Day-to-day costs (rent, fuel, salaries paid).", how: "Add each expense with a category so Profit & Loss is accurate." },
    ],
  },
  {
    group: "Work",
    items: [
      { to: "/projects", name: "Projects", what: "Larger pieces of work with an owner and status.", how: "Create a project and attach tasks to it." },
      { to: "/tasks", name: "Tasks", what: "Individual to-dos on a board (To do, In progress, Review, Done).", how: "Drag a task across columns as it moves along." },
      { to: "/tickets", name: "Support Tickets", what: "Customer problems that need tracking to a fix.", how: "Open a ticket, set priority, update status until it is resolved." },
      { to: "/documents", name: "Documents", what: "Shared file storage for contracts, invoices and notes.", how: "Upload a file and link it to the right record." },
    ],
  },
  {
    group: "System",
    items: [
      { to: "/audit", name: "Audit Log", what: "A record of who did what and when (sending a broadcast, importing contacts, changing data).", how: "Use it to answer 'who changed this?'." },
      { to: "/settings", name: "Settings", what: "Your security (two-factor sign-in) and the sync with the website store.", how: "Turn on 2FA. Use the sync buttons to pull the latest orders, sellers and deliveries from the website." },
    ],
  },
];

export default function Guide() {
  const [q, setQ] = useState("");
  const term = q.trim().toLowerCase();
  const groups = GUIDE.map((g) => ({
    ...g,
    items: g.items.filter((i) => !term || `${i.name} ${i.what} ${i.how}`.toLowerCase().includes(term)),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="space-y-6">
      <PageHeader testId="guide-page" title="How GLC Zone works" subtitle="What every page is for and how to use it" actions={
        <div className="relative">
          <Search size={14} className="absolute left-3 top-3 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the guide" className="h-10 pl-9 pr-3 rounded-lg border border-slate-200 bg-white text-[13px] w-64 outline-none focus:border-[hsl(var(--primary))]" />
        </div>
      } />
      {groups.length === 0 && <div className="text-center text-[13px] text-slate-500 py-16">Nothing matches "{q}"</div>}
      {groups.map((g) => (
        <section key={g.group}>
          <h2 className="text-[11px] uppercase tracking-[0.1em] font-semibold text-slate-500 mb-3">{g.group}</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {g.items.map((i) => (
              <Link key={i.to} to={i.to} className="group bg-white rounded-2xl border border-slate-200/70 card-elev p-4 hover:border-emerald-300 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="text-[14.5px] font-semibold text-slate-900">{i.name}</div>
                  <ArrowUpRight size={15} className="text-slate-300 group-hover:text-emerald-600" />
                </div>
                <p className="text-[13px] text-slate-600 mt-1.5">{i.what}</p>
                <p className="text-[12.5px] text-slate-500 mt-2"><span className="font-medium text-slate-700">How: </span>{i.how}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
