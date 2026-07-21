import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth, VerticalProvider } from "@/context/AuthContext";
import AppLayout from "@/components/Layout/AppLayout";
import CommandPalette from "@/components/CommandPalette";
import { canAccess } from "@/lib/rbac";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Leads from "@/pages/crm/Leads";
import Customers from "@/pages/crm/Customers";
import Customer360 from "@/pages/crm/Customer360";
import Pipeline from "@/pages/crm/Pipeline";
import Quotations from "@/pages/crm/Quotations";
import Orders from "@/pages/sales/Orders";
import Invoices from "@/pages/sales/Invoices";
import Products from "@/pages/inventory/Products";
import Stock from "@/pages/inventory/Stock";
import Suppliers from "@/pages/purchase/Suppliers";
import PurchaseOrders from "@/pages/purchase/PurchaseOrders";
import Deliveries from "@/pages/delivery/Deliveries";
import Employees from "@/pages/hr/Employees";
import Attendance from "@/pages/hr/Attendance";
import Leaves from "@/pages/hr/Leaves";
import Payroll from "@/pages/hr/Payroll";
import { ChartOfAccounts, Journal, GstReports, Expenses } from "@/pages/finance/Finance";
import { Projects, Tasks, Tickets, Documents, AuditLog, Settings } from "@/pages/misc/Misc";
import Inbox from "@/pages/ocm/Inbox";
import { OcmContacts, Broadcasts, Flows, SocialScheduler, ContentCalendar } from "@/pages/ocm/Ocm";
import { EmptyState } from "@/components/common/GlcUI";
import { Lock } from "lucide-react";
import { Toaster } from "sonner";
import { Loader2 } from "lucide-react";

function Guard({ children, module }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen grid place-items-center"><Loader2 className="animate-spin text-[hsl(var(--primary))]" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (module && !canAccess(user.role || "Admin", module)) {
    return (
      <AppLayout>
        <div className="pt-10">
          <EmptyState icon={Lock} title="Access restricted" description={`Your role (${user.role}) does not have permission to view this module. Please contact an admin.`} testId="access-denied" />
        </div>
      </AppLayout>
    );
  }
  return (
    <AppLayout>
      {children}
      <CommandPalette />
    </AppLayout>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Guard module="dashboard"><Dashboard /></Guard>} />
      <Route path="/crm/leads" element={<Guard module="crm.leads"><Leads /></Guard>} />
      <Route path="/crm/customers" element={<Guard module="crm.customers"><Customers /></Guard>} />
      <Route path="/crm/customers/:id" element={<Guard module="crm.customers"><Customer360 /></Guard>} />
      <Route path="/crm/pipeline" element={<Guard module="crm.pipeline"><Pipeline /></Guard>} />
      <Route path="/crm/quotations" element={<Guard module="crm.quotations"><Quotations /></Guard>} />
      <Route path="/sales/orders" element={<Guard module="sales.orders"><Orders /></Guard>} />
      <Route path="/sales/invoices" element={<Guard module="sales.invoices"><Invoices /></Guard>} />
      <Route path="/inventory/products" element={<Guard module="inventory.products"><Products /></Guard>} />
      <Route path="/inventory/stock" element={<Guard module="inventory.stock"><Stock /></Guard>} />
      <Route path="/purchase/suppliers" element={<Guard module="purchase.suppliers"><Suppliers /></Guard>} />
      <Route path="/purchase/orders" element={<Guard module="purchase.orders"><PurchaseOrders /></Guard>} />
      <Route path="/delivery" element={<Guard module="delivery"><Deliveries /></Guard>} />
      <Route path="/hr/employees" element={<Guard module="hr.employees"><Employees /></Guard>} />
      <Route path="/hr/attendance" element={<Guard module="hr.attendance"><Attendance /></Guard>} />
      <Route path="/hr/leaves" element={<Guard module="hr.leaves"><Leaves /></Guard>} />
      <Route path="/hr/payroll" element={<Guard module="hr.payroll"><Payroll /></Guard>} />
      <Route path="/finance/accounts" element={<Guard module="finance.accounts"><ChartOfAccounts /></Guard>} />
      <Route path="/finance/journal" element={<Guard module="finance.journal"><Journal /></Guard>} />
      <Route path="/finance/gst" element={<Guard module="finance.gst"><GstReports /></Guard>} />
      <Route path="/finance/expenses" element={<Guard module="finance.expenses"><Expenses /></Guard>} />
      <Route path="/projects" element={<Guard module="projects"><Projects /></Guard>} />
      <Route path="/tasks" element={<Guard module="tasks"><Tasks /></Guard>} />
      <Route path="/tickets" element={<Guard module="tickets"><Tickets /></Guard>} />
      <Route path="/documents" element={<Guard module="documents"><Documents /></Guard>} />
      <Route path="/ocm/inbox" element={<Guard module="ocm.inbox"><Inbox /></Guard>} />
      <Route path="/ocm/contacts" element={<Guard module="ocm.contacts"><OcmContacts /></Guard>} />
      <Route path="/ocm/broadcasts" element={<Guard module="ocm.broadcasts"><Broadcasts /></Guard>} />
      <Route path="/ocm/flows" element={<Guard module="ocm.flows"><Flows /></Guard>} />
      <Route path="/ocm/social" element={<Guard module="ocm.social"><SocialScheduler /></Guard>} />
      <Route path="/ocm/calendar" element={<Guard module="ocm.calendar"><ContentCalendar /></Guard>} />
      <Route path="/audit" element={<Guard module="audit"><AuditLog /></Guard>} />
      <Route path="/settings" element={<Guard module="settings"><Settings /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <VerticalProvider>
          <AppRoutes />
          <Toaster position="bottom-right" richColors closeButton />
        </VerticalProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
